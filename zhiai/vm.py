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

from zhiai.builtins import BUILTINS, ARRAY_METHODS, STRING_METHODS, ZhiAiError


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

    def __init__(self, instructions, return_addr, env=None, constants=None):
        self.instructions = instructions
        self.return_addr = return_addr
        self.env = env
        self.constants = constants


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
                
        # 如果是源码，需要先编译（这里简单起见，如果提供了解释器或预编译即可）
        # 我们在 VM 里统一当做 .zab 加载。如果是 .za，由于没有自举编译器环境，这里会报错，
        # 所以目前要求 `导入` 最好指向编译好的 .zab（即我们的 DLL）
        
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
            instr = self.instructions[self.ip]
            op = instr[0]
            self.ip += 1
            self.execute(op, instr[1:])

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

    def execute(self, op, args):
        """执行单条指令"""

        if op == "PUSH":
            self.push(self.constants[args[0]])

        elif op == "POP":
            self.pop()

        elif op == "DUP":
            self.push(self.peek())

        # ── 算术 ──
        elif op == "ADD":
            b, a = self.pop(), self.pop()
            if isinstance(a, str) or isinstance(b, str):
                self.push(self.to_str(a) + self.to_str(b))
            else:
                self.push(a + b)

        elif op == "SUB":
            b, a = self.pop(), self.pop()
            self.push(a - b)

        elif op == "MUL":
            b, a = self.pop(), self.pop()
            self.push(a * b)

        elif op == "DIV":
            b, a = self.pop(), self.pop()
            if b == 0:
                raise VMError("除以零")
            if isinstance(a, int) and isinstance(b, int) and a % b == 0:
                self.push(a // b)
            else:
                self.push(a / b)

        elif op == "MOD":
            b, a = self.pop(), self.pop()
            if b == 0:
                raise VMError("除以零")
            self.push(a % b)

        elif op == "POW":
            b, a = self.pop(), self.pop()
            self.push(a ** b)

        elif op == "NEG":
            self.push(-self.pop())

        # ── 比较 ──
        elif op == "EQ":
            b, a = self.pop(), self.pop()
            self.push(a == b)

        elif op == "NEQ":
            b, a = self.pop(), self.pop()
            self.push(a != b)

        elif op == "LT":
            b, a = self.pop(), self.pop()
            self.push(a < b)

        elif op == "GT":
            b, a = self.pop(), self.pop()
            self.push(a > b)

        elif op == "LTE":
            b, a = self.pop(), self.pop()
            self.push(a <= b)

        elif op == "GTE":
            b, a = self.pop(), self.pop()
            self.push(a >= b)

        # ── 逻辑 ──
        elif op == "AND":
            b, a = self.pop(), self.pop()
            self.push(self.is_truthy(a) and self.is_truthy(b))

        elif op == "OR":
            b, a = self.pop(), self.pop()
            self.push(self.is_truthy(a) or self.is_truthy(b))

        elif op == "NOT":
            self.push(not self.is_truthy(self.pop()))

        # ── 变量 ──
        elif op == "LOAD":
            name = self.constants[args[0]]
            env = self.call_stack[-1].env if self.call_stack else self.global_env
            self.push(env.get(name))

        elif op == "STORE":
            name = self.constants[args[0]]
            value = self.peek()
            env = self.call_stack[-1].env if self.call_stack else self.global_env
            env.set(name, value)

        elif op == "DEF":
            name = self.constants[args[0]]
            value = self.peek()
            env = self.call_stack[-1].env if self.call_stack else self.global_env
            env.define(name, value)

        # ── 索引 ──
        elif op == "LOAD_INDEX":
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

        elif op == "STORE_INDEX":
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

        elif op == "LOAD_PROP":
            prop = self.constants[args[0]]
            obj = self.pop()
            if isinstance(obj, dict):
                val = obj.get(prop)
                if val is not None:
                    self.push(val)
                elif prop in ARRAY_METHODS:
                    self.push(lambda *a: ARRAY_METHODS[prop](obj, *a))
                elif prop == "长度":
                    self.push(len(obj))
                else:
                    self.push(None)
            elif isinstance(obj, list):
                if prop == "长度":
                    self.push(len(obj))
                elif prop in ARRAY_METHODS:
                    self.push(lambda *a: ARRAY_METHODS[prop](obj, *a))
                else:
                    raise VMError(f"数组没有属性 '{prop}'")
            elif isinstance(obj, str):
                if prop == "长度":
                    self.push(len(obj))
                elif prop in STRING_METHODS:
                    self.push(lambda *a: STRING_METHODS[prop](obj, *a))
                else:
                    raise VMError(f"字符串没有属性 '{prop}'")
            else:
                raise VMError(f"无法访问属性: {type(obj).__name__}")

        elif op == "STORE_PROP":
            prop = self.constants[args[0]]
            value = self.pop()
            obj = self.pop()
            if isinstance(obj, dict):
                obj[prop] = value
            else:
                raise VMError(f"无法属性赋值: {type(obj).__name__}")
            self.push(value)

        # ── 调用 ──
        elif op == "CALL":
            argc = args[0]
            func_args = []
            for _ in range(argc):
                func_args.append(self.pop())
            func_args.reverse()
            callee = self.pop()

            if isinstance(callee, dict) and "type" in callee and callee["type"] == "function":
                # 用户定义的函数
                if len(func_args) != callee["arity"]:
                    raise VMError(
                        f"函数期望 {callee['arity']} 个参数，但得到 {len(func_args)} 个"
                    )
                func_env = Environment(callee.get("closure", self.global_env))
                # 参数覆盖闭包变量（参数优先级更高）
                for i, param in enumerate(callee["params"]):
                    func_env.define(param, func_args[i])
                frame = Frame(
                    instructions=self.instructions,
                    return_addr=self.ip,
                    env=func_env,
                    constants=self.constants
                )
                self.call_stack.append(frame)
                self.instructions = callee.get("instructions", self.instructions)
                self.constants = callee.get("constants", self.constants)
                self.ip = callee["instr_start"]
            elif callable(callee):
                # 内置函数
                try:
                    result = callee(*func_args)
                    self.push(result)
                except TypeError as e:
                    raise VMError(f"调用错误: {e}")
                except ZhiAiError as e:
                    raise VMError(str(e))
            else:
                raise VMError(f"无法调用: {type(callee).__name__}")

        elif op == "CALL_METHOD":
            method_name = self.constants[args[0]]
            argc = args[1]
            method_args = []
            for _ in range(argc):
                method_args.append(self.pop())
            method_args.reverse()
            obj = self.pop()

            if isinstance(obj, list):
                if method_name in ARRAY_METHODS:
                    self.push(ARRAY_METHODS[method_name](obj, *method_args))
                elif method_name == "长度":
                    self.push(len(obj))
                else:
                    raise VMError(f"数组没有方法 '{method_name}'")
            elif isinstance(obj, str):
                if method_name in STRING_METHODS:
                    self.push(STRING_METHODS[method_name](obj, *method_args))
                elif method_name == "长度":
                    self.push(len(obj))
                else:
                    raise VMError(f"字符串没有方法 '{method_name}'")
            elif isinstance(obj, dict):
                if method_name in obj:
                    func = obj[method_name]
                    if callable(func):
                        self.push(func(*method_args))
                    elif isinstance(func, dict) and func.get("type") == "function":
                        # 将对象本身作为隐式第一个参数压入？（致爱目前没有 this，所以直接当普通函数调）
                        if len(method_args) != func["arity"]:
                            raise VMError(
                                f"方法期望 {func['arity']} 个参数，但得到 {len(method_args)} 个"
                            )
                        func_env = Environment(func.get("closure", self.global_env))
                        for i, param in enumerate(func["params"]):
                            func_env.define(param, method_args[i])
                        frame = Frame(
                            instructions=self.instructions,
                            return_addr=self.ip,
                            env=func_env,
                            constants=self.constants
                        )
                        self.call_stack.append(frame)
                        self.instructions = func.get("instructions", self.instructions)
                        self.constants = func.get("constants", self.constants)
                        self.ip = func["instr_start"]
                    else:
                        raise VMError(f"对象属性 '{method_name}' 不是可调用函数")
                else:
                    raise VMError(f"对象没有方法 '{method_name}'")
            else:
                raise VMError(f"无法调用方法: {type(obj).__name__}")

        elif op == "MAKE_FUNC":
            name = self.constants[args[0]]
            arity = args[1]
            param_count = args[2]
            params = []
            for i in range(param_count):
                params.append(self.constants[args[3 + i]])
            instr_start = args[3 + param_count]
            # 捕获闭包：保存当前作用域环境
            closure_env = self.call_stack[-1].env if self.call_stack else self.global_env
            func = {
                "type": "function",
                "name": name,
                "arity": arity,
                "params": params,
                "instr_start": instr_start,
                "closure": closure_env,
                "instructions": self.instructions,
                "constants": self.constants
            }
            self.push(func)
            if name:
                if self.call_stack:
                    self.call_stack[-1].env.define(name, func)
                else:
                    self.global_env.define(name, func)

        elif op == "RET":
            value = self.pop()
            if not self.call_stack:
                # 顶层返回
                self.halted = True
                self.push(value)
                return
            frame = self.call_stack.pop()
            self.instructions = frame.instructions
            self.constants = getattr(frame, "constants", self.constants) or self.constants
            self.ip = frame.return_addr
            self.push(value)

        # ── 控制流 ──
        elif op == "JMP":
            self.ip = args[0]

        elif op == "JMP_IF":
            value = self.pop()
            if self.is_truthy(value):
                self.ip = args[0]

        elif op == "JMP_IFNOT":
            value = self.pop()
            if not self.is_truthy(value):
                self.ip = args[0]

        # ── 数据构造 ──
        elif op == "MAKE_ARRAY":
            count = args[0]
            arr = []
            for _ in range(count):
                arr.append(self.pop())
            arr.reverse()
            self.push(arr)

        elif op == "MAKE_OBJECT":
            count = args[0]
            obj = {}
            for _ in range(count):
                value = self.pop()
                key = self.pop()
                obj[key] = value
            self.push(obj)

        # ── 特殊 ──
        elif op == "PRINT":
            value = self.pop()
            print(self.to_str(value))

        elif op == "HALT":
            self.halted = True

        else:
            raise VMError(f"未知指令: {op}")


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
