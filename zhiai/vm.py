"""致爱字节码虚拟机 — 执行 .zab 字节码文件

字节码格式 (JSON):
{
  "constants": [...],      # 常量池
  "instructions": [...],   # 指令流 [opcode, arg1, arg2, ...]
  "globals": {}            # 初始全局变量（可选）
}

指令集:
  PUSH <值>           压入常量
  POP                 弹出栈顶
  ADD / SUB / MUL / DIV / MOD / POW   算术
  NEG                 取负
  EQ / NEQ / LT / GT / LTE / GTE     比较
  AND / OR / NOT       逻辑
  LOAD <名称>         加载变量
  STORE <名称>        存储变量
  LOAD_INDEX          索引加载 arr[idx]
  STORE_INDEX         索引存储 arr[idx] = val
  LOAD_PROP <名称>    属性加载 obj.prop
  STORE_PROP <名称>   属性存储 obj.prop = val
  CALL <参数数>       调用函数
  RET                 返回
  JMP <偏移>          无条件跳转
  JMP_IF <偏移>       条件跳转(真)
  JMP_IFNOT <偏移>    条件跳转(假)
  MAKE_ARRAY <数量>   创建数组
  MAKE_OBJECT <数量>  创建对象
  DUP                 复制栈顶
  PRINT               输出栈顶
  HALT                停止
"""

import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zhiai.builtins import BUILTINS, ARRAY_METHODS, STRING_METHODS, BATCH_FUNC_MAP, ZhiAiError
from zhiai.shapes import EMPTY_SHAPE


class VMError(Exception):
    pass


class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent
        
    def get(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise VMError(f"未定义的变量: '{name}'")
        
    def set(self, name, value):
        env = self
        while env:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        raise VMError(f"未定义的变量: '{name}'")
        
    def define(self, name, value):
        self.vars[name] = value

class Frame:
    """函数调用帧"""

    def __init__(self, instructions, return_addr, env=None, constants=None, locals_count=0):
        self.instructions = instructions
        self.return_addr = return_addr
        self.env = env
        self.constants = constants
        # 使用列表存储局部变量，索引访问提升性能
        self.locals = [None] * locals_count
        self.locals_count = locals_count
        # 异常处理栈: (handler_ip, stack_size)
        self.exception_handlers = []


class Instance:
    """类实例，使用 Shape 优化属性存储"""
    def __init__(self, klass):
        self.klass = klass
        self.shape = EMPTY_SHAPE
        self.fields = []

    def get_prop(self, name):
        offset = self.shape.get_offset(name)
        if offset is not None:
            return self.fields[offset]
        # 检查类方法
        if name in self.klass["methods"]:
            return self.klass["methods"][name]
        return None

    def set_prop(self, name, value):
        offset = self.shape.get_offset(name)
        if offset is not None:
            self.fields[offset] = value
        else:
            self.shape = self.shape.transition(name)
            self.fields.append(value)


class VM:
    """字节码虚拟机"""

    def __init__(self):
        self.stack = []
        self.global_env = Environment()
        self.call_stack = []
        self.ip = 0  # 指令指针
        self.instructions = []
        self.constants = []
        self.halted = False
        # 指令分发表，映射 opcode 到实现方法
        self._dispatch = {
            "PUSH": self._op_PUSH,
            "POP": self._op_POP,
            "DUP": self._op_DUP,
            "ADD": self._op_ADD,
            "SUB": self._op_SUB,
            "MUL": self._op_MUL,
            "DIV": self._op_DIV,
            "MOD": self._op_MOD,
            "POW": self._op_POW,
            "NEG": self._op_NEG,
            "EQ": self._op_EQ,
            "NEQ": self._op_NEQ,
            "LT": self._op_LT,
            "GT": self._op_GT,
            "LTE": self._op_LTE,
            "GTE": self._op_GTE,
            "AND": self._op_AND,
            "OR": self._op_OR,
            "NOT": self._op_NOT,
            "LOAD": self._op_LOAD,
            "STORE": self._op_STORE,
            "DEF": self._op_DEF,
            "LOAD_INDEX": self._op_LOAD_INDEX,
            "STORE_INDEX": self._op_STORE_INDEX,
            "LOAD_PROP": self._op_LOAD_PROP,
            "STORE_PROP": self._op_STORE_PROP,
            "CALL": self._op_CALL,
            "RET": self._op_RET,
            "JMP": self._op_JMP,
            "JMP_IF": self._op_JMP_IF,
            "JMP_IFNOT": self._op_JMP_IFNOT,
            "HALT": self._op_HALT,
            "BATCH_OP": self._op_BATCH_OP,
            "TRY": self._op_TRY,
            "END_TRY": self._op_END_TRY,
            "RAISE": self._op_RAISE,
            "MAKE_CLASS": self._op_MAKE_CLASS,
            "NEW": self._op_NEW,
            "BREAKPOINT": self._op_BREAKPOINT,
            # 特化指令
            "LOAD_LOCAL": self._op_LOAD_LOCAL,
            "STORE_LOCAL": self._op_STORE_LOCAL,
            "LOAD_GLOBAL": self._op_LOAD_GLOBAL,
            "STORE_GLOBAL": self._op_STORE_GLOBAL,
            "FAST_ADD": self._op_FAST_ADD,
            "FAST_SUB": self._op_FAST_SUB,
            "BINOP": self._op_BINOP,
        }

        # 注册内置函数
        for name, func in BUILTINS.items():
            self.global_env.define(name, func)

        # 注册 导入 函数
        self.global_env.define("导入", self._builtin_import)

    def _builtin_import(self, module_path):
        """导入模块并返回其导出的全局变量字典"""
        if not os.path.exists(module_path):
            # 尝试加上 .zab 或 .za 后缀
            if os.path.exists(module_path + ".zab"):
                module_path += ".zab"
            elif os.path.exists(module_path + ".za"):
                module_path += ".za"
            else:
                raise VMError(f"导入失败: 找不到模块 '{module_path}'")
                
        # 为了通用性，启动一个新的 VM 实例
        sub_vm = VM()
        
        if module_path.endswith(".za"):
            # 将 .za 编译为 .zab 再加载
            zab_path = module_path + "b"
            import subprocess
            # 找到 zhiai_cli.py
            cli_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "zhiai_cli.py")
            if getattr(sys, 'frozen', False):
                # 如果是 exe 运行，调用自己 compile
                subprocess.run([sys.executable, "compile", module_path, "-o", zab_path], check=True, stdout=subprocess.DEVNULL)
            else:
                subprocess.run([sys.executable, cli_path, "compile", module_path, "-o", zab_path], check=True, stdout=subprocess.DEVNULL)
            module_path = zab_path
            
        # 默认视为 .zab 加载
        sub_vm.load_file(module_path)
        sub_vm.run()
        # 提取 VM 的全局变量（排除内置函数）
        exports = {}
        for k, v in sub_vm.global_env.vars.items():
            if k not in BUILTINS and k != "导入":
                exports[k] = v
        return exports

    def load(self, bytecode):
        """加载字节码"""
        if isinstance(bytecode, str):
            bytecode = json.loads(bytecode)
        self.constants = bytecode.get("constants", [])
        self.instructions = bytecode.get("instructions", [])
        user_globals = bytecode.get("globals", {})
        for k, v in user_globals.items():
            self.global_env.define(k, v)

    def load_file(self, path):
        """从文件加载字节码"""
        with open(path, "r", encoding="utf-8") as f:
            self.load(f.read())

    def run(self):
        """执行字节码"""
        self.ip = 0
        self.halted = False

        while not self.halted and self.ip < len(self.instructions):
            try:
                instr = self.instructions[self.ip]
                op = instr[0]
                self.ip += 1
                handler = self._dispatch.get(op)
                if handler is None:
                    raise VMError(f"未知指令: {op}")
                # 性能优化：直接传递整个指令，避免切片产生新列表
                handler(instr)
            except Exception as e:
                self._handle_exception(e)

    def _handle_exception(self, e):
        """处理异常：查找最近的捕获点"""
        if self.call_stack:
            frame = self.call_stack[-1]
            if frame.exception_handlers:
                handler_ip, saved_stack_size = frame.exception_handlers.pop()
                # 恢复栈深度，压入错误对象
                while len(self.stack) > saved_stack_size:
                    self.pop()
                self.push(str(e))
                self.ip = handler_ip
                return
        
        # 如果没有局部处理，则向上传播
        if self.call_stack:
            self.call_stack.pop()
            if self.call_stack:
                last_frame = self.call_stack[-1]
                self.instructions = last_frame.instructions
                self.constants = last_frame.constants
                self.ip = last_frame.return_addr
                self._handle_exception(e)
                return
        
        # 顶层异常
        print(f"致命错误: {e}", file=sys.stderr)
        self.halted = True

    def push(self, value):
        self.stack.append(value)

    def pop(self):
        if not self.stack:
            raise VMError("栈为空")
        return self.stack.pop()

    def peek(self):
        if not self.stack:
            raise VMError("栈为空")
        return self.stack[-1]

    def to_str(self, value):
        if value is None:
            return "空"
        if isinstance(value, bool):
            return "真" if value else "假"
        if isinstance(value, float):
            if value == int(value):
                return str(int(value))
        return str(value)

    def is_truthy(self, value):
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, list):
            return len(value) > 0
        if isinstance(value, dict):
            return len(value) > 0
        return True

    def _op_PUSH(self, instr):
        self.push(self.constants[instr[1]])

    def _op_POP(self, instr):
        self.pop()

    def _op_DUP(self, instr):
        self.push(self.peek())

    def _op_ADD(self, instr):
        b, a = self.pop(), self.pop()
        if isinstance(a, str) or isinstance(b, str):
            self.push(self.to_str(a) + self.to_str(b))
        else:
            self.push(a + b)

    def _op_FAST_ADD(self, instr):
        b, a = self.pop(), self.pop()
        self.push(a + b)

    def _op_SUB(self, instr):
        b, a = self.pop(), self.pop()
        self.push(a - b)

    def _op_FAST_SUB(self, instr):
        b, a = self.pop(), self.pop()
        self.push(a - b)

    def _op_MUL(self, instr):
        b, a = self.pop(), self.pop()
        self.push(a * b)

    def _op_DIV(self, instr):
        b, a = self.pop(), self.pop()
        if b == 0:
            raise VMError("除以零")
        if isinstance(a, int) and isinstance(b, int) and a % b == 0:
            self.push(a // b)
        else:
            self.push(a / b)

    def _op_MOD(self, instr):
        b, a = self.pop(), self.pop()
        if b == 0:
            raise VMError("除以零")
        self.push(a % b)

    def _op_POW(self, instr):
        b, a = self.pop(), self.pop()
        self.push(a ** b)

    def _op_NEG(self, instr):
        self.push(-self.pop())

    def _op_EQ(self, instr):
        b, a = self.pop(), self.pop()
        self.push(a == b)

    def _op_NEQ(self, instr):
        b, a = self.pop(), self.pop()
        self.push(a != b)

    def _op_LT(self, instr):
        b, a = self.pop(), self.pop()
        self.push(a < b)

    def _op_GT(self, instr):
        b, a = self.pop(), self.pop()
        self.push(a > b)

    def _op_LTE(self, instr):
        b, a = self.pop(), self.pop()
        self.push(a <= b)

    def _op_GTE(self, instr):
        b, a = self.pop(), self.pop()
        self.push(a >= b)

    def _op_AND(self, instr):
        b, a = self.pop(), self.pop()
        self.push(self.is_truthy(a) and self.is_truthy(b))

    def _op_OR(self, instr):
        b, a = self.pop(), self.pop()
        self.push(self.is_truthy(a) or self.is_truthy(b))

    def _op_NOT(self, instr):
        self.push(not self.is_truthy(self.pop()))

    def _op_LOAD(self, args):
        name = self.constants[args[0]]
        env = self.call_stack[-1].env if self.call_stack else self.global_env
        self.push(env.get(name))

    def _op_STORE(self, args):
        name = self.constants[args[0]]
        value = self.peek()
        env = self.call_stack[-1].env if self.call_stack else self.global_env
        env.set(name, value)

    def _op_DEF(self, instr):
        name = self.constants[instr[1]]
        value = self.peek()
        env = self.call_stack[-1].env if self.call_stack else self.global_env
        env.define(name, value)

    def _op_LOAD_LOCAL(self, instr):
        self.push(self.call_stack[-1].locals[instr[1]])

    def _op_STORE_LOCAL(self, instr):
        self.call_stack[-1].locals[instr[1]] = self.pop()

    def _op_LOAD_GLOBAL(self, instr):
        self.push(self.global_env.get(self.constants[instr[1]]))

    def _op_STORE_GLOBAL(self, instr):
        self.global_env.set(self.constants[instr[1]], self.pop())

    def _op_BINOP(self, instr):
        op = instr[1]
        b, a = self.pop(), self.pop()
        if op == '+': self.push(a + b)
        elif op == '-': self.push(a - b)
        elif op == '*': self.push(a * b)
        elif op == '/': self.push(a / b)

    def _op_LOAD_INDEX(self, instr):
        index = self.pop()
        obj = self.pop()
        if isinstance(obj, list):
            idx = int(index)
            if idx < 0:
                idx += len(obj)
            self.push(obj[idx])
        elif isinstance(obj, dict):
            self.push(obj.get(index))
        elif isinstance(obj, str):
            idx = int(index)
            if idx < 0:
                idx += len(obj)
            self.push(obj[idx])
        else:
            raise VMError(f"无法索引: {type(obj).__name__}")

    def _op_STORE_INDEX(self, instr):
        index = self.pop()
        obj = self.pop()
        value = self.pop()
        if isinstance(obj, list):
            obj[int(index)] = value
        elif isinstance(obj, dict):
            obj[index] = value
        else:
            raise VMError(f"无法索引赋值: {type(obj).__name__}")
        self.push(value)

    def _op_LOAD_PROP(self, instr):
        name = self.constants[instr[1]]
        obj = self.pop()
        if isinstance(obj, Instance):
            self.push(obj.get_prop(name))
        elif isinstance(obj, dict):
            self.push(obj.get(name))
        elif isinstance(obj, str):
            if name == "长度":
                self.push(len(obj))
            elif name in STRING_METHODS:
                self.push(lambda *a: STRING_METHODS[name](obj, *a))
            else:
                raise VMError(f"字符串没有方法: {name}")
        elif isinstance(obj, list):
            if name == "长度":
                self.push(len(obj))
            elif name in ARRAY_METHODS:
                self.push(lambda *a: ARRAY_METHODS[name](obj, *a))
            else:
                raise VMError(f"数组没有方法: {name}")
        else:
            self.push(getattr(obj, name, None))

    def _op_STORE_PROP(self, instr):
        name = self.constants[instr[1]]
        val = self.pop()
        obj = self.pop()
        if isinstance(obj, Instance):
            obj.set_prop(name, val)
        elif isinstance(obj, dict):
            obj[name] = val
        else:
            setattr(obj, name, val)
        self.push(val)

    def _op_CALL(self, instr):
        argc = instr[1]
        func_args = [self.pop() for _ in range(argc)]
        func_args.reverse()
        callee = self.pop()

        # 检测尾调用：如果 callee 为用户定义函数且其指令最后为 RET 且当前帧即将返回
        if isinstance(callee, dict) and "type" in callee and callee["type"] == "function":
            # 参数检查
            if len(func_args) != callee.get("arity", 0):
                raise VMError(f"函数期望 {callee.get('arity',0)} 个参数，但得到 {len(func_args)} 个")
            # 判断是否为尾调用（当前帧没有后续指令）
            if self.ip == len(self.instructions):
                # 复用当前帧的 locals
                current_frame = self.call_stack[-1] if self.call_stack else None
                if current_frame:
                    # 写入新参数到当前帧的 locals（按顺序）
                    for i, param in enumerate(callee.get("params", [])):
                        current_frame.locals[i] = func_args[i]
                    # 跳转到函数体开始
                    self.instructions = callee["instructions"]
                    self.constants = callee.get("constants", [])
                    self.ip = 0
                    return
            # 常规函数调用，创建新帧
            func_env = Environment(callee.get("closure", self.global_env))
            for i, param in enumerate(callee.get("params", [])):
                func_env.define(param, func_args[i])
            frame = Frame(callee["instructions"], self.ip, env=func_env, constants=self.constants, locals_count=callee.get("locals_count", 0))
            self.call_stack.append(frame)
            self.instructions = callee["instructions"]
            self.constants = callee.get("constants", [])
            self.ip = 0
            return
        # 处理内置函数或可调用对象
        result = callee(*func_args)
        self.push(result)

    def _op_RET(self, instr):
        # 返回值
        ret_val = self.pop()
        if not self.call_stack:
            # 主程序返回，停止运行
            self.halted = True
            self.push(ret_val)
            return
        frame = self.call_stack.pop()
        # 恢复调用者上下文
        self.instructions = frame.instructions
        self.constants = frame.constants
        self.ip = frame.return_addr
        self.push(ret_val)

    def _op_JMP(self, instr):
        self.ip = instr[1]

    def _op_JMP_IF(self, instr):
        offset = instr[1]
        if self.is_truthy(self.pop()):
            self.ip = offset

    def _op_JMP_IFNOT(self, instr):
        offset = instr[1]
        if not self.is_truthy(self.pop()):
            self.ip = offset

    def _op_MAKE_ARRAY(self, instr):
        count = instr[1]
        arr = []
        for _ in range(count):
            arr.append(self.pop())
        arr.reverse()
        self.push(arr)

    def _op_MAKE_OBJECT(self, instr):
        count = instr[1]
        obj = {}
        for _ in range(count):
            value = self.pop()
            key = self.pop()
            obj[key] = value
        self.push(obj)

    def _op_PRINT(self, instr):
        value = self.pop()
        print(self.to_str(value))

    def _op_HALT(self, instr):
        self.halted = True

    def _op_BATCH_OP(self, instr):
        # instr: [BATCH_OP, func_id, arg_count]
        func_id = instr[1]
        arg_count = instr[2]
        # 弹出参数
        params = [self.pop() for _ in range(arg_count)]
        params.reverse()
        # 调用批处理函数映射（在 builtins 中维护 BATCH_FUNC_MAP）
        batch_func = BATCH_FUNC_MAP.get(func_id)
        if batch_func is None:
            raise VMError(f"未知批处理指令 ID: {func_id}")
        result = batch_func(*params)
        self.push(result)

    def _op_TRY(self, instr):
        handler_ip = instr[1]
        if self.call_stack:
            self.call_stack[-1].exception_handlers.append((handler_ip, len(self.stack)))
        else:
            # 顶层也可以有简单的异常处理逻辑（视具体实现而定）
            pass

    def _op_END_TRY(self, instr):
        if self.call_stack and self.call_stack[-1].exception_handlers:
            self.call_stack[-1].exception_handlers.pop()

    def _op_RAISE(self, instr):
        msg = self.pop()
        raise VMError(str(msg))

    def _op_MAKE_CLASS(self, instr):
        name = self.constants[instr[1]]
        methods = self.pop() # 一个字典
        klass = {"type": "class", "name": name, "methods": methods}
        self.global_env.define(name, klass)
        self.push(klass)

    def _op_NEW(self, instr):
        klass = self.pop()
        instance = Instance(klass)
        self.push(instance)
        # 检查是否有构造函数
        if "构造" in klass["methods"]:
            constructor = klass["methods"]["构造"]
            # 自动调用构造函数（这里简化逻辑，实际需要压入参数并 CALL）
            pass


    def _op_BREAKPOINT(self, instr):
        print(f"\n[调试] 触发断点 IP: {self.ip}")
        print(f"  栈: {self.stack}")
        if self.call_stack:
            print(f"  局部变量: {self.call_stack[-1].locals}")
        input("按 Enter 继续执行...")

def run_file(path):
    """执行 .zab 字节码文件"""
    vm = VM()
    vm.load_file(path)
    vm.run()


def main():
    if len(sys.argv) < 2:
        print("用法: python -m zhiai.vm <文件.zab>", file=sys.stderr)
        sys.exit(1)
    run_file(sys.argv[1])


if __name__ == "__main__":
    main()
