# cython: language_level=3
"""致爱高速虚拟机 — Cython 编译加速实现"""

import json
import os
import sys

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


OPCODE_LIST = [
    "PUSH", "POP", "DUP", "ADD", "SUB", "MUL", "DIV", "MOD", "POW", "NEG",
    "EQ", "NEQ", "LT", "GT", "LTE", "GTE", "AND", "OR", "NOT", "LOAD",
    "STORE", "DEF", "LOAD_INDEX", "STORE_INDEX", "LOAD_PROP", "STORE_PROP",
    "CALL", "RET", "JMP", "JMP_IF", "JMP_IFNOT", "HALT", "BATCH_OP", "TRY",
    "END_TRY", "RAISE", "MAKE_CLASS", "MAKE_ARRAY", "MAKE_OBJECT", "PRINT",
    "NEW", "BREAKPOINT", "MAKE_FUNC", "CALL_METHOD", "LOAD_LOCAL", "STORE_LOCAL",
    "LOAD_GLOBAL", "STORE_GLOBAL", "FAST_ADD", "FAST_SUB", "BINOP"
]
OPCODE_MAP = {op: i for i, op in enumerate(OPCODE_LIST)}


class Frame:
    """函数调用帧"""
    def __init__(self, instructions, int return_addr, env=None, constants=None, int locals_count=0, bint is_constructor=False, instance=None):
        self.instructions = instructions
        self.return_addr = return_addr
        self.env = env
        self.constants = constants
        self.locals = [None] * locals_count
        self.locals_count = locals_count
        self.exception_handlers = []
        self.is_constructor = is_constructor
        self.instance = instance


class FramePool:
    """Frame 缓存池，规避垃圾回收与对象创建开销"""
    def __init__(self):
        self.pool = []

    def acquire(self, instructions, int return_addr, env=None, constants=None, int locals_count=0, bint is_constructor=False, instance=None):
        if self.pool:
            frame = self.pool.pop()
            frame.instructions = instructions
            frame.return_addr = return_addr
            frame.env = env
            frame.constants = constants
            # 极速重置 locals 数组
            if len(frame.locals) < locals_count:
                frame.locals = [None] * locals_count
            else:
                for i in range(locals_count):
                    frame.locals[i] = None
            frame.locals_count = locals_count
            frame.exception_handlers.clear()
            frame.is_constructor = is_constructor
            frame.instance = instance
            return frame
        else:
            return Frame(instructions, return_addr, env, constants, locals_count, is_constructor, instance)

    def release(self, frame):
        frame.env = None
        frame.constants = None
        frame.instance = None
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
    """致爱高速虚拟机"""
    def __init__(self):
        self.stack = []
        self.global_env = Environment()
        self.call_stack = []
        self.ip = 0
        self.instructions = []
        self.constants = []
        self.halted = False
        self.exception_handlers = []
        self.frame_pool = FramePool()
        
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
            "LOAD_LOCAL": self._op_LOAD_LOCAL,
            "STORE_LOCAL": self._op_STORE_LOCAL,
            "LOAD_GLOBAL": self._op_LOAD_GLOBAL,
            "STORE_GLOBAL": self._op_STORE_GLOBAL,
            "FAST_ADD": self._op_FAST_ADD,
            "FAST_SUB": self._op_FAST_SUB,
            "BINOP": self._op_BINOP,
        }

        self._dispatch_list = [None] * len(OPCODE_LIST)
        for op_str, handler in self._dispatch.items():
            idx = OPCODE_MAP.get(op_str)
            if idx is not None:
                self._dispatch_list[idx] = handler

        for name, func in BUILTINS.items():
            self.global_env.define(name, func)
        self.global_env.define("导入", self._builtin_import)

    def _builtin_import(self, module_path):
        if not os.path.exists(module_path):
            if os.path.exists(module_path + ".zab"):
                module_path += ".zab"
            elif os.path.exists(module_path + ".za"):
                module_path += ".za"
            else:
                raise VMError(f"导入失败: 找不到模块 '{module_path}'")
                
        sub_vm = VM()
        if module_path.endswith(".za"):
            zab_path = module_path + "b"
            import subprocess
            cli_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "zhiai_cli.py")
            if getattr(sys, 'frozen', False):
                subprocess.run([sys.executable, "compile", module_path, "-o", zab_path], check=True, stdout=subprocess.DEVNULL)
            else:
                subprocess.run([sys.executable, cli_path, "compile", module_path, "-o", zab_path], check=True, stdout=subprocess.DEVNULL)
            module_path = zab_path
            
        sub_vm.load_file(module_path)
        sub_vm.run()
        exports = {}
        for k, v in sub_vm.global_env.vars.items():
            if k not in BUILTINS and k != "导入":
                exports[k] = v
        return exports

    def load(self, bytecode):
        if isinstance(bytecode, str):
            bytecode = json.loads(bytecode)
        self.constants = bytecode.get("constants", [])
        
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
                op_int = <int>instr[0]
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
        import zhiai.builtins as builtins
        old_vm = builtins.CURRENT_VM
        builtins.CURRENT_VM = self

        cdef int ip = self.ip
        cdef list instructions = self.instructions
        cdef list dispatch_list = self._dispatch_list
        cdef bint halted = self.halted

        try:
            while not self.halted and self.ip < len(self.instructions):
                try:
                    instr = self.instructions[self.ip]
                    op_int = <int>instr[0]
                    self.ip += 1
                    dispatch_list[op_int](instr)
                except Exception as e:
                    self._handle_exception(e)
        finally:
            builtins.CURRENT_VM = old_vm

    def _handle_exception(self, e):
        if self.call_stack:
            frame = self.call_stack[-1]
            if frame.exception_handlers:
                handler_ip, saved_stack_size = frame.exception_handlers.pop()
                while len(self.stack) > saved_stack_size:
                    self.pop()
                self.push(str(e))
                self.ip = handler_ip
                return
        else:
            if self.exception_handlers:
                handler_ip, saved_stack_size = self.exception_handlers.pop()
                while len(self.stack) > saved_stack_size:
                    self.pop()
                self.push(str(e))
                self.ip = handler_ip
                return
        
        if self.call_stack:
            frame = self.call_stack.pop()
            self.frame_pool.release(frame)
            if self.call_stack:
                last_frame = self.call_stack[-1]
                self.instructions = last_frame.instructions
                self.constants = last_frame.constants
                self.ip = last_frame.return_addr
                self._handle_exception(e)
                return
        
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
            # Inline Cache (IC) check
            if len(instr) > 3 and obj.shape is instr[2]:
                self.push(obj.fields[instr[3]])
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
                self.push(obj.fields[offset])
            else:
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
                if len(func_args) != callee.get("arity", 0):
                    raise VMError(f"函数期望 {callee.get('arity',0)} 个参数，但得到 {len(func_args)} 个")
                if self.ip == len(self.instructions):
                    current_frame = self.call_stack[-1] if self.call_stack else None
                    if current_frame:
                        for i, param in enumerate(callee.get("params", [])):
                            current_frame.locals[i] = func_args[i]
                        self.instructions = callee["instructions"]
                        self.constants = callee.get("constants", [])
                        self.ip = callee.get("entry_ip", 0)
                        return
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

        result = callee(*func_args)
        self.push(result)

    def _op_RET(self, instr):
        ret_val = self.pop()
        if not self.call_stack:
            self.halted = True
            if self.stack and self.stack[-1] is ret_val:
                pass
            else:
                self.push(ret_val)
            return
        frame = self.call_stack.pop()
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
        func_id = instr[1]
        arg_count = instr[2]
        params = [self.pop() for _ in range(arg_count)]
        params.reverse()
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
        methods = self.pop()
        klass = {"type": "class", "name": name, "methods": methods}
        self.global_env.define(name, klass)
        self.push(klass)

    def _op_NEW(self, instr):
        klass = self.pop()
        instance = Instance(klass)
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

    def _op_BREAKPOINT(self, instr):
        print(f"\n[调试] 触发断点 IP: {self.ip}")
        print(f"  栈: {self.stack}")
        if self.call_stack:
            print(f"  局部变量: {self.call_stack[-1].locals}")
        input("按 Enter 继续执行...")
