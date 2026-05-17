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
from zhiai.gc import MarkSweepGC


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

OPCODE_LIST = [
    "PUSH", "POP", "DUP", "ADD", "SUB", "MUL", "DIV", "MOD", "POW", "NEG",
    "EQ", "NEQ", "LT", "GT", "LTE", "GTE", "AND", "OR", "NOT", "LOAD",
    "STORE", "DEF", "LOAD_INDEX", "STORE_INDEX", "LOAD_PROP", "STORE_PROP",
    "CALL", "RET", "JMP", "JMP_IF", "JMP_IFNOT", "HALT", "BATCH_OP", "TRY",
    "END_TRY", "RAISE", "MAKE_CLASS", "MAKE_ARRAY", "MAKE_OBJECT", "PRINT",
    "NEW", "BREAKPOINT", "MAKE_FUNC", "CALL_METHOD", "LOAD_LOCAL", "STORE_LOCAL",
    "LOAD_GLOBAL", "STORE_GLOBAL", "FAST_ADD", "FAST_SUB", "BINOP",
    "ASYNC_CALL", "AWAIT"
]
OPCODE_MAP = {op: i for i, op in enumerate(OPCODE_LIST)}


class Frame:
    """函数调用帧"""

    def __init__(self, instructions, return_addr, env=None, constants=None, locals_count=0, is_constructor=False, instance=None):
        self.instructions = instructions
        self.return_addr = return_addr
        self.env = env
        self.constants = constants
        # 使用列表存储局部变量，索引访问提升性能
        self.locals = [None] * locals_count
        self.locals_count = locals_count
        # 异常处理栈: (handler_ip, stack_size)
        self.exception_handlers = []
        self.deferred = []
        self.is_constructor = is_constructor
        self.instance = instance


class FramePool:
    """对象池，用于重用 Frame 实例以降低 GC 和对象分配开销"""
    def __init__(self):
        self.pool = []

    def acquire(self, instructions, return_addr, env=None, constants=None, locals_count=0, is_constructor=False, instance=None):
        if self.pool:
            frame = self.pool.pop()
            frame.instructions = instructions
            frame.return_addr = return_addr
            frame.env = env
            frame.constants = constants
            if frame.locals_count >= locals_count:
                for i in range(locals_count):
                    frame.locals[i] = None
            else:
                frame.locals = [None] * locals_count
            frame.locals_count = locals_count
            frame.exception_handlers.clear()
            frame.deferred = []
            frame.is_constructor = is_constructor
            frame.instance = instance
            return frame
        else:
            return Frame(instructions, return_addr, env, constants, locals_count, is_constructor, instance)

    def release(self, frame):
        frame.env = None
        frame.constants = None
        frame.instance = None
        frame.deferred = []
        self.pool.append(frame)


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
        self.exception_handlers = []
        self.frame_pool = FramePool()
        self.deferred = []
        self.gc = MarkSweepGC(self)
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
            "MAKE_ARRAY": self._op_MAKE_ARRAY,
            "MAKE_OBJECT": self._op_MAKE_OBJECT,
            "PRINT": self._op_PRINT,
            "NEW": self._op_NEW,
            "BREAKPOINT": self._op_BREAKPOINT,
            "MAKE_FUNC": self._op_MAKE_FUNC,
            "CALL_METHOD": self._op_CALL_METHOD,
            # 特化指令
            "LOAD_LOCAL": self._op_LOAD_LOCAL,
            "STORE_LOCAL": self._op_STORE_LOCAL,
            "LOAD_GLOBAL": self._op_LOAD_GLOBAL,
            "STORE_GLOBAL": self._op_STORE_GLOBAL,
            "FAST_ADD": self._op_FAST_ADD,
            "FAST_SUB": self._op_FAST_SUB,
            "BINOP": self._op_BINOP,
            "ASYNC_CALL": self._op_ASYNC_CALL,
            "AWAIT": self._op_AWAIT,
        }

        # 构建整数索引跳转表
        self._dispatch_list = [None] * len(OPCODE_LIST)
        for op_str, handler in self._dispatch.items():
            idx = OPCODE_MAP.get(op_str)
            if idx is not None:
                self._dispatch_list[idx] = handler

        # 注册内置函数
        for name, func in BUILTINS.items():
            self.global_env.define(name, func)

        # 注册 导入 函数
        self.global_env.define("导入", self._builtin_import)
        self.global_env.define("垃圾回收", self.gc.collect)

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
        
        # 将指令中的字符串 opcode 转换为整数，提高分发效率
        loaded_instructions = bytecode.get("instructions", [])
        self.instructions = []
        for instr in loaded_instructions:
            if instr and isinstance(instr[0], str):
                op_int = OPCODE_MAP.get(instr[0])
                if op_int is None:
                    raise VMError(f"未知指令字符串: {instr[0]}")
                self.instructions.append([op_int] + list(instr[1:]))
            else:
                self.instructions.append(instr)

        user_globals = bytecode.get("globals", {})
        for k, v in user_globals.items():
            self.global_env.define(k, v)

    def load_file(self, path):
        """从文件加载字节码，自动识别并加载二进制 marshal 格式或传统 JSON 格式"""
        with open(path, "rb") as f:
            header = f.read(4)
            if header == b"ZAB\x00":
                import marshal
                try:
                    bytecode = marshal.load(f)
                    self.load(bytecode)
                except Exception as e:
                    raise VMError(f"加载二进制字节码失败: {e}")
            else:
                f.seek(0)
                try:
                    content = f.read().decode("utf-8")
                    self.load(content)
                except Exception as e:
                    raise VMError(f"加载字节码失败: {e}")

    def call_function_nested(self, func, args):
        """在当前 VM 上嵌套调用一个致爱函数并返回结果，支持 Python 原生回调"""
        old_ip = self.ip
        old_instr = self.instructions
        old_consts = self.constants
        old_halted = self.halted
        
        func_env = Environment(func.get("closure", self.global_env))
        for i, param in enumerate(func.get("params", [])):
            if i < len(args):
                func_env.define(param, args[i])
            else:
                func_env.define(param, None)
            
        frame = self.frame_pool.acquire(
            func["instructions"],
            return_addr=-1,
            env=func_env,
            constants=self.constants,
            locals_count=func.get("locals_count", 50)
        )
        for i in range(min(len(args), len(frame.locals))):
            frame.locals[i] = args[i]
            
        self.call_stack.append(frame)
        self.instructions = func["instructions"]
        self.constants = func.get("constants", [])
        self.ip = func.get("entry_ip", 0)
        self.halted = False
        
        saved_stack_depth = len(self.stack)
        saved_call_stack_depth = len(self.call_stack)
        
        dispatch_list = self._dispatch_list
        while not self.halted and len(self.call_stack) >= saved_call_stack_depth:
            try:
                instr = self.instructions[self.ip]
                op_int = instr[0]
                self.ip += 1
                dispatch_list[op_int](instr)
            except Exception as e:
                self._handle_exception(e)
                if self.halted:
                    break
        
        ret_val = None
        if len(self.stack) > saved_stack_depth:
            ret_val = self.pop()
            
        self.ip = old_ip
        self.instructions = old_instr
        self.constants = old_consts
        self.halted = old_halted
        
        return ret_val

    def run(self):
        """执行字节码"""
        import zhiai.builtins as builtins
        old_vm = builtins.CURRENT_VM
        builtins.CURRENT_VM = self

        self.ip = 0
        self.halted = False

        try:
            dispatch_list = self._dispatch_list
            while not self.halted and self.ip < len(self.instructions):
                try:
                    instr = self.instructions[self.ip]
                    op_int = instr[0]
                    self.ip += 1
                    dispatch_list[op_int](instr)
                except Exception as e:
                    self._handle_exception(e)
        finally:
            if self.deferred:
                for cb in reversed(self.deferred):
                    try:
                        self.call_function_nested(cb, [])
                    except Exception as e_defer:
                        print(f"延迟函数执行出错: {e_defer}", file=sys.stderr)
            builtins.CURRENT_VM = old_vm

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
        else:
            if self.exception_handlers:
                handler_ip, saved_stack_size = self.exception_handlers.pop()
                # 恢复栈深度，压入错误对象
                while len(self.stack) > saved_stack_size:
                    self.pop()
                self.push(str(e))
                self.ip = handler_ip
                return
        
        # 如果没有局部处理，则向上传播
        if self.call_stack:
            frame = self.call_stack.pop()
            # 执行延迟函数
            if frame.deferred:
                for cb in reversed(frame.deferred):
                    try:
                        self.call_function_nested(cb, [])
                    except Exception as e_defer:
                        print(f"延迟函数执行出错: {e_defer}", file=sys.stderr)
            self.frame_pool.release(frame)
            if self.call_stack:
                last_frame = self.call_stack[-1]
                self.instructions = last_frame.instructions
                self.constants = last_frame.constants
                self.ip = last_frame.return_addr
                self._handle_exception(e)
                return
        
        # 顶层异常
        print(f"致命错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
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
            if value != value:
                return "NaN"
            if value == float('inf'):
                return "Infinity"
            if value == float('-inf'):
                return "-Infinity"
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
        name = self.constants[args[1]]
        env = self.call_stack[-1].env if self.call_stack else self.global_env
        self.push(env.get(name))

    def _op_STORE(self, args):
        name = self.constants[args[1]]
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
        self.call_stack[-1].locals[instr[1]] = self.peek()

    def _op_LOAD_GLOBAL(self, instr):
        self.push(self.global_env.get(self.constants[instr[1]]))

    def _op_STORE_GLOBAL(self, instr):
        self.global_env.set(self.constants[instr[1]], self.peek())

    def _op_BINOP(self, instr):
        op = instr[1]
        b, a = self.pop(), self.pop()
        if op == '+':
            if isinstance(a, str) or isinstance(b, str):
                self.push(self.to_str(a) + self.to_str(b))
            else:
                self.push(a + b)
        elif op == '-': self.push(a - b)
        elif op == '*': self.push(a * b)
        elif op == '/':
            if b == 0:
                raise VMError("除以零")
            if isinstance(a, int) and isinstance(b, int) and a % b == 0:
                self.push(a // b)
            else:
                self.push(a / b)

    def _op_LOAD_INDEX(self, instr):
        index = self.pop()
        obj = self.pop()
        if isinstance(obj, (list, str)):
            idx = int(index)
            if idx < 0: idx += len(obj)
            if idx < 0 or idx >= len(obj):
                raise VMError(f"索引越界: {idx} (长度: {len(obj)})")
            self.push(obj[idx])
        elif isinstance(obj, dict):
            self.push(obj.get(index))
        else:
            raise VMError(f"无法索引: {type(obj).__name__}")

    def _op_STORE_INDEX(self, instr):
        index = self.pop()
        obj = self.pop()
        value = self.pop()
        if isinstance(obj, list):
            idx = int(index)
            if idx < 0: idx += len(obj)
            if idx < 0 or idx >= len(obj):
                raise VMError(f"索引赋值越界: {idx} (长度: {len(obj)})")
            obj[idx] = value
        elif isinstance(obj, dict):
            obj[index] = value
        else:
            raise VMError(f"无法索引赋值: {type(obj).__name__}")
        self.push(value)

    def _op_LOAD_PROP(self, instr):
        name = self.constants[instr[1]]
        obj = self.pop()
        if isinstance(obj, Instance):
            # Polymorphic Inline Cache (PIC) check
            if len(instr) > 2:
                cache_type = instr[2]
                if cache_type == 'MONO':
                    if obj.shape is instr[3]:
                        self.push(obj.fields[instr[4]])
                        return
                    else:
                        # Transition to POLY
                        mono_shape = instr[3]
                        mono_offset = instr[4]
                        instr[2] = 'POLY'
                        instr[3] = [(mono_shape, mono_offset)]
                        # Fall through to slow path / add new entry
                elif cache_type == 'POLY':
                    # Search in cache list
                    cache_list = instr[3]
                    for cached_shape, offset in cache_list:
                        if obj.shape is cached_shape:
                            self.push(obj.fields[offset])
                            return
                    # Fall through to slow path / add new entry
                elif cache_type == 'MEGA':
                    pass # MEGA state: directly fall through to slow path

            # Slow path
            offset = obj.shape.get_offset(name)
            if offset is not None:
                # Cache the shape and offset
                if len(instr) == 2:
                    instr.extend(['MONO', obj.shape, offset])
                elif instr[2] == 'POLY':
                    cache_list = instr[3]
                    if len(cache_list) < 4:
                        cache_list.append((obj.shape, offset))
                    else:
                        instr[2] = 'MEGA'
                self.push(obj.fields[offset])
            else:
                # Check class methods
                if name in obj.klass["methods"]:
                    self.push(obj.klass["methods"][name])
                else:
                    self.push(None)
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
        obj = self.pop()
        val = self.pop()
        if isinstance(obj, Instance):
            # Inline Cache (IC) check
            if len(instr) > 3 and obj.shape is instr[2]:
                obj.fields[instr[3]] = val
                self.push(val)
                return
            
            # Slow path
            offset = obj.shape.get_offset(name)
            if offset is not None:
                # Cache the shape and offset
                if len(instr) == 2:
                    instr.extend([obj.shape, offset])
                else:
                    instr[2] = obj.shape
                    instr[3] = offset
                obj.fields[offset] = val
            else:
                # Transition shape (property doesn't exist yet)
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

        if isinstance(callee, dict) and "type" in callee:
            if callee["type"] == "class":
                # 类实例化
                instance = Instance(callee)
                if "构造" in callee["methods"]:
                    constructor = callee["methods"]["构造"]
                    if len(func_args) != constructor.get("arity", 0):
                        raise VMError(f"构造函数期望 {constructor.get('arity', 0)} 个参数，但得到 {len(func_args)} 个")
                    func_env = Environment(constructor.get("closure", self.global_env))
                    func_env.define("这", instance)
                    for i, param in enumerate(constructor.get("params", [])):
                        func_env.define(param, func_args[i])
                    frame = self.frame_pool.acquire(
                        constructor["instructions"],
                        self.ip,
                        env=func_env,
                        constants=self.constants,
                        locals_count=constructor.get("locals_count", 0),
                        is_constructor=True,
                        instance=instance
                    )
                    self.call_stack.append(frame)
                    for i in range(len(func_args)):
                        frame.locals[i] = func_args[i]
                    self.instructions = constructor["instructions"]
                    self.constants = constructor.get("constants", [])
                    self.ip = constructor.get("entry_ip", 0)
                    return
                else:
                    self.push(instance)
                    return

            if callee["type"] == "function":
                # JIT 检查与运行时动态编译
                if "jit_count" not in callee:
                    callee["jit_count"] = 0
                    callee["jitted_func"] = None
                
                callee["jit_count"] += 1
                if callee["jit_count"] > 15 and callee["jitted_func"] is None:
                    from zhiai.vm_jit import compile_function
                    callee["jitted_func"] = compile_function(callee, self.global_env)
                    
                if callee["jitted_func"] is not None:
                    # 快速路径：直接执行 JIT 编译的原生 Python 代码！
                    locals_count = callee.get("locals_count", 0)
                    locals_list = func_args + [None] * (locals_count - len(func_args))
                    res = callee["jitted_func"](locals_list, self.global_env)
                    self.push(res)
                    return

                # 参数检查
                if len(func_args) != callee.get("arity", 0):
                    raise VMError(f"函数期望 {callee.get('arity',0)} 个参数，但得到 {len(func_args)} 个")
                # 判断是否为尾调用（当前帧没有后续指令）
                if self.ip == len(self.instructions):
                    # 复用当前帧的 locals
                    current_frame = self.call_stack[-1] if self.call_stack else None
                    if current_frame:
                        for i, param in enumerate(callee.get("params", [])):
                            current_frame.locals[i] = func_args[i]
                        self.instructions = callee["instructions"]
                        self.constants = callee.get("constants", [])
                        self.ip = callee.get("entry_ip", 0)
                        return
                # 常规函数调用，创建新帧
                func_env = Environment(callee.get("closure", self.global_env))
                for i, param in enumerate(callee.get("params", [])):
                    func_env.define(param, func_args[i])
                frame = self.frame_pool.acquire(callee["instructions"], self.ip, env=func_env, constants=self.constants, locals_count=callee.get("locals_count", 0))
                self.call_stack.append(frame)
                for i in range(len(func_args)):
                    frame.locals[i] = func_args[i]
                self.instructions = callee["instructions"]
                self.constants = callee.get("constants", [])
                self.ip = callee.get("entry_ip", 0)
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
            if self.stack and self.stack[-1] is ret_val:
                pass
            else:
                self.push(ret_val)
            return
        frame = self.call_stack.pop()
        # 执行延迟函数
        if frame.deferred:
            for cb in reversed(frame.deferred):
                try:
                    self.call_function_nested(cb, [])
                except Exception as e_defer:
                    print(f"延迟函数执行出错: {e_defer}", file=sys.stderr)
        # 恢复调用者上下文
        self.instructions = frame.instructions
        self.constants = frame.constants
        self.ip = frame.return_addr
        if frame.is_constructor:
            self.push(frame.instance)
        else:
            self.push(ret_val)
        self.frame_pool.release(frame)

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
        self.gc.track(arr)
        self.push(arr)

    def _op_MAKE_OBJECT(self, instr):
        count = instr[1]
        obj = {}
        for _ in range(count):
            value = self.pop()
            key = self.pop()
            obj[key] = value
        self.gc.track(obj)
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
            self.exception_handlers.append((handler_ip, len(self.stack)))

    def _op_END_TRY(self, instr):
        if self.call_stack:
            if self.call_stack[-1].exception_handlers:
                self.call_stack[-1].exception_handlers.pop()
        else:
            if self.exception_handlers:
                self.exception_handlers.pop()

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
        self.gc.track(instance)
        # 检查是否有构造函数
        if "构造" in klass["methods"]:
            constructor = klass["methods"]["构造"]
            # 构造函数处理与 _op_CALL 逻辑对齐
            func_env = Environment(constructor.get("closure", self.global_env))
            func_env.define("这", instance)
            frame = self.frame_pool.acquire(
                constructor["instructions"],
                self.ip,
                env=func_env,
                constants=self.constants,
                locals_count=constructor.get("locals_count", 0),
                is_constructor=True,
                instance=instance
            )
            self.call_stack.append(frame)
            self.instructions = constructor["instructions"]
            self.constants = constructor.get("constants", [])
            self.ip = constructor.get("entry_ip", 0)
        else:
            self.push(instance)

    def _op_MAKE_FUNC(self, instr):
        name = self.constants[instr[1]]
        arity = instr[2]
        param_count = instr[3]
        params = [self.constants[instr[4 + i]] for i in range(param_count)]
        entry_ip = instr[4 + param_count]
        
        func = {
            "type": "function",
            "name": name,
            "arity": arity,
            "params": params,
            "entry_ip": entry_ip,
            "instructions": self.instructions,
            "constants": self.constants,
            "closure": self.call_stack[-1].env if self.call_stack else self.global_env,
            "locals_count": 50
        }
        
        env = self.call_stack[-1].env if self.call_stack else self.global_env
        env.define(name, func)
        self.push(func)

    def _op_CALL_METHOD(self, instr):
        method_name = self.constants[instr[1]]
        argc = instr[2]
        func_args = [self.pop() for _ in range(argc)]
        func_args.reverse()
        obj = self.pop()

        if isinstance(obj, Instance):
            # 1. 尝试使用方法内联缓存 (Method Inline Cache Hit)
            if len(instr) > 4 and obj.klass is instr[3]:
                method = instr[4]
            else:
                # 2. 慢速路径并写入缓存
                method = obj.klass["methods"].get(method_name)
                if method is not None:
                    if len(instr) == 3:
                        instr.extend([obj.klass, method])
                    else:
                        instr[3] = obj.klass
                        instr[4] = method

            if method is None:
                raise VMError(f"类 '{obj.klass['name']}' 没有方法 '{method_name}'")
            if len(func_args) != method.get("arity", 0):
                raise VMError(f"方法 '{method_name}' 期望 {method.get('arity',0)} 个参数，但得到 {len(func_args)} 个")
            func_env = Environment(method.get("closure", self.global_env))
            func_env.define("这", obj)
            for i, param in enumerate(method.get("params", [])):
                func_env.define(param, func_args[i])
            frame = self.frame_pool.acquire(
                method["instructions"],
                self.ip,
                env=func_env,
                constants=self.constants,
                locals_count=method.get("locals_count", 0)
            )
            self.call_stack.append(frame)
            for i in range(len(func_args)):
                frame.locals[i] = func_args[i]
            self.instructions = method["instructions"]
            self.constants = method.get("constants", [])
            self.ip = method.get("entry_ip", 0)
            return

        elif isinstance(obj, list):
            if method_name in ARRAY_METHODS:
                res = ARRAY_METHODS[method_name](obj, *func_args)
                self.push(res)
                return
            elif method_name == "长度":
                self.push(len(obj))
                return
            else:
                raise VMError(f"数组没有方法 '{method_name}'")

        elif isinstance(obj, str):
            if method_name in STRING_METHODS:
                res = STRING_METHODS[method_name](obj, *func_args)
                self.push(res)
                return
            elif method_name == "长度":
                self.push(len(obj))
                return
            else:
                raise VMError(f"字符串没有方法 '{method_name}'")

        elif isinstance(obj, dict):
            if method_name in obj:
                method = obj[method_name]
                if isinstance(method, dict) and "type" in method and method["type"] == "function":
                    func_env = Environment(method.get("closure", self.global_env))
                    func_env.define("这", obj)
                    for i, param in enumerate(method.get("params", [])):
                        func_env.define(param, func_args[i])
                    frame = Frame(
                        method["instructions"],
                        self.ip,
                        env=func_env,
                        constants=self.constants,
                        locals_count=method.get("locals_count", 0)
                    )
                    self.call_stack.append(frame)
                    self.instructions = method["instructions"]
                    self.constants = method.get("constants", [])
                    self.ip = method.get("entry_ip", 0)
                    return
                elif callable(method):
                    res = method(*func_args)
                    self.push(res)
                    return
                else:
                    raise VMError(f"属性 '{method_name}' 不是可调用的方法")
            else:
                raise VMError(f"对象没有属性或方法 '{method_name}'")

        else:
            method = getattr(obj, method_name, None)
            if callable(method):
                res = method(*func_args)
                self.push(res)
                return
            else:
                raise VMError(f"类型 {type(obj).__name__} 没有方法或属性 '{method_name}'")


    def _op_ASYNC_CALL(self, instr):
        argc = instr[1]
        args = [self.pop() for _ in range(argc)]
        args.reverse()
        callee = self.pop()
        
        # 简单实现：使用线程池模拟异步
        import concurrent.futures
        from zhiai.builtins import wrap_callable
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        wrapped = wrap_callable(callee)
        future = executor.submit(wrapped, *args)
        self.push(future)

    def _op_AWAIT(self, instr):
        future = self.pop()
        if hasattr(future, "result"):
            res = future.result() # 阻塞等待
            self.push(res)
        else:
            self.push(future)

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
