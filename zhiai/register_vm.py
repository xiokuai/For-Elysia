"""致爱寄存器虚拟机 — 执行 .zab 字节码文件 (v1.1.0 架构)"""

import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zhiai.builtins import BUILTINS, ARRAY_METHODS, STRING_METHODS, BATCH_FUNC_MAP, ZhiAiError
from zhiai.shapes import EMPTY_SHAPE
from zhiai.gc import IncrementalGC


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
    "LOAD_CONST", "LOAD_GLOBAL", "STORE_GLOBAL", "DEF_GLOBAL", 
    "MOVE", "LOAD_NULL", "LOAD_BOOL",
    "ADD", "SUB", "MUL", "DIV", "MOD", "POW", 
    "EQ", "NEQ", "LT", "GT", "LTE", "GTE", 
    "NEG", "NOT",
    "LOAD_INDEX", "STORE_INDEX", "LOAD_PROP", "STORE_PROP",
    "JMP", "JMP_IF", "JMP_IFNOT",
    "CALL", "CALL_METHOD", "RET",
    "MAKE_FUNC", "MAKE_ARRAY", "MAKE_OBJECT", "MAKE_CLASS", "NEW",
    "TRY", "END_TRY", "RAISE", "TRY_PROPAGATE",
    "PRINT", "HALT", "BREAKPOINT",
    "ASYNC_CALL", "AWAIT", "BATCH_OP"
]
OPCODE_MAP = {op: i for i, op in enumerate(OPCODE_LIST)}


class Frame:
    """函数调用帧"""
    def __init__(self, instructions, return_addr, env=None, constants=None, return_reg=None, is_constructor=False, instance=None):
        self.instructions = instructions
        self.return_addr = return_addr
        self.env = env
        self.constants = constants
        self.registers = [None] * 256
        self.exception_handlers = []
        self.deferred = []
        self.return_reg = return_reg
        self.is_constructor = is_constructor
        self.instance = instance


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


class RegisterVM:
    """基于寄存器的虚拟机"""

    def __init__(self):
        self.global_env = Environment()
        self.call_stack = []
        self.ip = 0
        self.instructions = []
        self.constants = []
        self.halted = False
        self.exception_handlers = []
        self.deferred = []
        self.gc = IncrementalGC(self)

        # 注册内置函数
        for name, func in BUILTINS.items():
            self.global_env.define(name, func)

        self.global_env.define("导入", self._builtin_import)
        self.global_env.define("垃圾回收", self.gc.collect)

        self._dispatch_list = [None] * len(OPCODE_LIST)
        for op in OPCODE_LIST:
            handler_name = f"_op_{op}"
            if hasattr(self, handler_name):
                self._dispatch_list[OPCODE_MAP[op]] = getattr(self, handler_name)

    def _builtin_import(self, module_path):
        """导入模块并返回其导出的全局变量字典"""
        if not os.path.exists(module_path):
            if os.path.exists(module_path + ".zab"): module_path += ".zab"
            elif os.path.exists(module_path + ".za"): module_path += ".za"
            else: raise VMError(f"导入失败: 找不到模块 '{module_path}'")
                
        sub_vm = RegisterVM()
        
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
        from zhiai.builtins import _成功
        return _成功(exports)

    def load(self, bytecode):
        """加载字节码"""
        if isinstance(bytecode, str):
            bytecode = json.loads(bytecode)
        self.constants = bytecode.get("constants", [])
        
        loaded_instructions = bytecode.get("instructions", [])
        self.instructions = []
        for instr in loaded_instructions:
            if instr and isinstance(instr[0], str):
                op_int = OPCODE_MAP.get(instr[0])
                if op_int is None: raise VMError(f"未知指令字符串: {instr[0]}")
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
        from zhiai.builtins import wrap_callable
        wrapped = wrap_callable(func)
        return wrapped(*args)

    def run(self):
        import zhiai.builtins as builtins
        old_vm = getattr(builtins, 'CURRENT_VM', None)
        builtins.CURRENT_VM = self

        self.ip = 0
        self.halted = False

        try:
            dispatch_list = self._dispatch_list
            instructions = self.instructions
            while not self.halted and self.ip < len(instructions):
                try:
                    instr = instructions[self.ip]
                    op_int = instr[0]
                    self.ip += 1
                    dispatch_list[op_int](instr)
                except Exception as e:
                    self._handle_exception(e)
        finally:
            if self.deferred:
                for cb in reversed(self.deferred):
                    try: self.call_function_nested(cb, [])
                    except Exception as e_defer: print(f"延迟函数执行出错: {e_defer}", file=sys.stderr)
            builtins.CURRENT_VM = old_vm

    def _handle_exception(self, e):
        if self.call_stack:
            frame = self.call_stack[-1]
            if frame.exception_handlers:
                handler_ip, catch_reg = frame.exception_handlers.pop()
                frame.registers[catch_reg] = str(e)
                self.ip = handler_ip
                return
        else:
            if self.exception_handlers:
                handler_ip, catch_reg = self.exception_handlers.pop()
                # Assuming top-level registers
                # Wait, top-level doesn't have frame.registers, it needs global handling or something.
                # Actually, top-level shouldn't have exceptions caught easily, or we can just use a global register array.
                # Let's say we have a dummy frame for top-level.
                pass
        
        if self.call_stack:
            frame = self.call_stack.pop()
            if frame.deferred:
                for cb in reversed(frame.deferred):
                    try: self.call_function_nested(cb, [])
                    except: pass
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

    def is_truthy(self, value):
        if value is None: return False
        if isinstance(value, bool): return value
        if isinstance(value, (int, float)): return value != 0
        if isinstance(value, str): return len(value) > 0
        if isinstance(value, list): return len(value) > 0
        if isinstance(value, dict): return len(value) > 0
        return True

    def to_str(self, value):
        if value is None: return "空"
        if isinstance(value, bool): return "真" if value else "假"
        if isinstance(value, float):
            if value != value: return "NaN"
            if value == float('inf'): return "Infinity"
            if value == float('-inf'): return "-Infinity"
            if value == int(value): return str(int(value))
        return str(value)

    # --- Registers ---
    @property
    def r(self):
        # We need a top-level register array for script execution.
        if not hasattr(self, '_top_r'):
            self._top_r = [None] * 256
        if self.call_stack:
            return self.call_stack[-1].registers
        return self._top_r

    def env(self):
        return self.call_stack[-1].env if self.call_stack else self.global_env

    # --- Opcodes ---
    def _op_LOAD_CONST(self, instr):
        self.r[instr[1]] = self.constants[instr[2]]

    def _op_LOAD_GLOBAL(self, instr):
        self.r[instr[1]] = self.env().get(self.constants[instr[2]])

    def _op_STORE_GLOBAL(self, instr):
        self.env().set(self.constants[instr[1]], self.r[instr[2]])

    def _op_DEF_GLOBAL(self, instr):
        self.env().define(self.constants[instr[1]], self.r[instr[2]])

    def _op_MOVE(self, instr):
        self.r[instr[1]] = self.r[instr[2]]

    def _op_LOAD_NULL(self, instr):
        self.r[instr[1]] = None

    def _op_LOAD_BOOL(self, instr):
        self.r[instr[1]] = bool(instr[2])

    def _op_ADD(self, instr):
        a = self.r[instr[2]]
        b = self.r[instr[3]]
        if isinstance(a, str) or isinstance(b, str):
            self.r[instr[1]] = self.to_str(a) + self.to_str(b)
        else:
            self.r[instr[1]] = a + b

    def _op_SUB(self, instr):
        self.r[instr[1]] = self.r[instr[2]] - self.r[instr[3]]

    def _op_MUL(self, instr):
        self.r[instr[1]] = self.r[instr[2]] * self.r[instr[3]]

    def _op_DIV(self, instr):
        a = self.r[instr[2]]
        b = self.r[instr[3]]
        if b == 0: raise VMError("除以零")
        if isinstance(a, int) and isinstance(b, int) and a % b == 0:
            self.r[instr[1]] = a // b
        else:
            self.r[instr[1]] = a / b

    def _op_MOD(self, instr):
        b = self.r[instr[3]]
        if b == 0: raise VMError("除以零")
        self.r[instr[1]] = self.r[instr[2]] % b

    def _op_POW(self, instr):
        self.r[instr[1]] = self.r[instr[2]] ** self.r[instr[3]]

    def _op_EQ(self, instr):
        self.r[instr[1]] = self.r[instr[2]] == self.r[instr[3]]

    def _op_NEQ(self, instr):
        self.r[instr[1]] = self.r[instr[2]] != self.r[instr[3]]

    def _op_LT(self, instr):
        self.r[instr[1]] = self.r[instr[2]] < self.r[instr[3]]

    def _op_GT(self, instr):
        self.r[instr[1]] = self.r[instr[2]] > self.r[instr[3]]

    def _op_LTE(self, instr):
        self.r[instr[1]] = self.r[instr[2]] <= self.r[instr[3]]

    def _op_GTE(self, instr):
        self.r[instr[1]] = self.r[instr[2]] >= self.r[instr[3]]

    def _op_NEG(self, instr):
        self.r[instr[1]] = -self.r[instr[2]]

    def _op_NOT(self, instr):
        self.r[instr[1]] = not self.is_truthy(self.r[instr[2]])

    def _op_LOAD_INDEX(self, instr):
        obj = self.r[instr[2]]
        idx_val = self.r[instr[3]]
        if isinstance(obj, (list, str)):
            idx = int(idx_val)
            if idx < 0: idx += len(obj)
            if idx < 0 or idx >= len(obj): raise VMError(f"索引越界: {idx}")
            self.r[instr[1]] = obj[idx]
        elif isinstance(obj, dict):
            self.r[instr[1]] = obj.get(idx_val)
        else:
            raise VMError("无法索引非数组/对象")

    def _op_STORE_INDEX(self, instr):
        obj = self.r[instr[1]]
        idx_val = self.r[instr[2]]
        val = self.r[instr[3]]
        if isinstance(obj, list):
            idx = int(idx_val)
            if idx < 0: idx += len(obj)
            if idx < 0 or idx >= len(obj): raise VMError(f"索引赋值越界: {idx}")
            obj[idx] = val
        elif isinstance(obj, dict):
            obj[idx_val] = val
        else:
            raise VMError("无法索引赋值非数组/对象")

    def _op_LOAD_PROP(self, instr):
        obj = self.r[instr[2]]
        name = self.constants[instr[3]]
        if isinstance(obj, Instance):
            self.r[instr[1]] = obj.get_prop(name)
        elif isinstance(obj, dict):
            self.r[instr[1]] = obj.get(name)
        elif isinstance(obj, str):
            if name == "长度": self.r[instr[1]] = len(obj)
            elif name in STRING_METHODS: self.r[instr[1]] = lambda *a: STRING_METHODS[name](obj, *a)
            else: raise VMError(f"字符串没有方法: {name}")
        elif isinstance(obj, list):
            if name == "长度": self.r[instr[1]] = len(obj)
            elif name in ARRAY_METHODS: self.r[instr[1]] = lambda *a: ARRAY_METHODS[name](obj, *a)
            else: raise VMError(f"数组没有方法: {name}")
        else:
            self.r[instr[1]] = getattr(obj, name, None)

    def _op_STORE_PROP(self, instr):
        obj = self.r[instr[1]]
        name = self.constants[instr[2]]
        val = self.r[instr[3]]
        if isinstance(obj, Instance):
            obj.set_prop(name, val)
        elif isinstance(obj, dict):
            obj[name] = val
        else:
            setattr(obj, name, val)

    def _op_JMP(self, instr):
        self.ip = instr[1]

    def _op_JMP_IF(self, instr):
        if self.is_truthy(self.r[instr[1]]):
            self.ip = instr[2]

    def _op_JMP_IFNOT(self, instr):
        if not self.is_truthy(self.r[instr[1]]):
            self.ip = instr[2]

    def _op_CALL(self, instr):
        # CALL dest, callee, arg_start, arg_count
        dest = instr[1]
        callee = self.r[instr[2]]
        arg_start = instr[3]
        arg_count = instr[4]
        
        args = [self.r[arg_start + i] for i in range(arg_count)]
        
        if isinstance(callee, dict) and "type" in callee:
            if callee["type"] == "class":
                instance = Instance(callee)
                if "构造" in callee["methods"]:
                    constructor = callee["methods"]["构造"]
                    func_env = Environment(constructor.get("closure", self.global_env))
                    func_env.define("这", instance)
                    for i, param in enumerate(constructor.get("params", [])):
                        if i < len(args): func_env.define(param, args[i])
                        else: func_env.define(param, None)
                    frame = Frame(
                        constructor["instructions"],
                        self.ip,
                        env=func_env,
                        constants=self.constants,
                        return_reg=dest,
                        is_constructor=True,
                        instance=instance
                    )
                    self.call_stack.append(frame)
                    self.instructions = constructor["instructions"]
                    self.constants = constructor.get("constants", [])
                    self.ip = constructor.get("entry_ip", 0)
                    return
                else:
                    self.r[dest] = instance
                    return

            if callee["type"] == "function":
                # Regular call
                func_env = Environment(callee.get("closure", self.global_env))
                for i, param in enumerate(callee.get("params", [])):
                    if i < len(args): func_env.define(param, args[i])
                    else: func_env.define(param, None)
                
                # Setup new frame
                frame = Frame(callee["instructions"], self.ip, env=func_env, constants=self.constants, return_reg=dest)
                # Map args to registers 0, 1, 2...
                for i in range(len(args)):
                    frame.registers[i] = args[i]
                
                self.call_stack.append(frame)
                self.instructions = callee["instructions"]
                self.constants = callee.get("constants", [])
                self.ip = callee.get("entry_ip", 0)
                return

        # Builtin / Native call
        from zhiai.builtins import wrap_callable
        res = wrap_callable(callee)(*args)
        self.r[dest] = res

    def _op_CALL_METHOD(self, instr):
        # CALL_METHOD dest, obj_reg, name_idx, arg_start, arg_count
        dest = instr[1]
        obj = self.r[instr[2]]
        method_name = self.constants[instr[3]]
        arg_start = instr[4]
        arg_count = instr[5]
        
        args = [self.r[arg_start + i] for i in range(arg_count)]
        
        if isinstance(obj, Instance):
            method = obj.klass["methods"].get(method_name)
            if method is None: raise VMError(f"类没有方法 '{method_name}'")
            func_env = Environment(method.get("closure", self.global_env))
            func_env.define("这", obj)
            for i, param in enumerate(method.get("params", [])):
                if i < len(args): func_env.define(param, args[i])
                else: func_env.define(param, None)
            frame = Frame(
                method["instructions"],
                self.ip,
                env=func_env,
                constants=self.constants,
                return_reg=dest
            )
            self.call_stack.append(frame)
            for i in range(len(args)):
                frame.registers[i] = args[i]
            self.instructions = method["instructions"]
            self.constants = method.get("constants", [])
            self.ip = method.get("entry_ip", 0)
            return
            
        elif isinstance(obj, list) and method_name in ARRAY_METHODS:
            self.r[dest] = ARRAY_METHODS[method_name](obj, *args)
            return
        elif isinstance(obj, str) and method_name in STRING_METHODS:
            self.r[dest] = STRING_METHODS[method_name](obj, *args)
            return
        
        method = getattr(obj, method_name, None)
        if callable(method):
            self.r[dest] = method(*args)
        else:
            raise VMError(f"类型无法调用方法 '{method_name}'")

    def _op_RET(self, instr):
        ret_val = self.r[instr[1]]
        if not self.call_stack:
            self.halted = True
            # To retrieve final value
            self.r[0] = ret_val
            return
            
        frame = self.call_stack.pop()
        if frame.deferred:
            for cb in reversed(frame.deferred):
                try: self.call_function_nested(cb, [])
                except: pass
                
        self.instructions = frame.instructions
        self.constants = frame.constants
        self.ip = frame.return_addr
        
        if frame.is_constructor:
            self.r[frame.return_reg] = frame.instance
        else:
            if frame.return_reg is not None:
                self.r[frame.return_reg] = ret_val

    def _op_MAKE_FUNC(self, instr):
        dest = instr[1]
        name_idx = instr[2]
        arity = instr[3]
        param_count = instr[4]
        param_start = instr[5]
        entry_ip = instr[6]
        
        name = self.constants[name_idx]
        params = [self.constants[param_start + i] for i in range(param_count)]
        
        func = {
            "type": "function",
            "name": name,
            "arity": arity,
            "params": params,
            "entry_ip": entry_ip,
            "instructions": self.instructions,
            "constants": self.constants,
            "closure": self.env()
        }
        
        self.env().define(name, func)
        self.r[dest] = func

    def _op_MAKE_ARRAY(self, instr):
        dest = instr[1]
        start = instr[2]
        count = instr[3]
        self.r[dest] = [self.r[start + i] for i in range(count)]

    def _op_MAKE_OBJECT(self, instr):
        dest = instr[1]
        start = instr[2]
        count = instr[3]
        obj = {}
        for i in range(count):
            key = self.r[start + i * 2]
            val = self.r[start + i * 2 + 1]
            obj[key] = val
        self.r[dest] = obj

    def _op_MAKE_CLASS(self, instr):
        dest = instr[1]
        name = self.constants[instr[2]]
        methods = self.r[instr[3]]
        klass = {"type": "class", "name": name, "methods": methods}
        self.env().define(name, klass)
        self.r[dest] = klass

    def _op_NEW(self, instr):
        dest = instr[1]
        klass = self.r[instr[2]]
        instance = Instance(klass)
        self.r[dest] = instance

    def _op_TRY(self, instr):
        handler_ip = instr[1]
        catch_reg = instr[2]
        if self.call_stack:
            self.call_stack[-1].exception_handlers.append((handler_ip, catch_reg))
        else:
            self.exception_handlers.append((handler_ip, catch_reg))

    def _op_END_TRY(self, instr):
        if self.call_stack:
            if self.call_stack[-1].exception_handlers:
                self.call_stack[-1].exception_handlers.pop()
        else:
            if self.exception_handlers:
                self.exception_handlers.pop()

    def _op_RAISE(self, instr):
        raise VMError(str(self.r[instr[1]]))

    def _op_TRY_PROPAGATE(self, instr):
        dest = instr[1]
        src = instr[2]
        val = self.r[src]
        if hasattr(val, "是失败") and val.是失败():
            self._op_RET(["RET", src])
            return
        if hasattr(val, "是空") and val.是空():
            self._op_RET(["RET", src])
            return
        if hasattr(val, "获取"):
            self.r[dest] = val.获取()
        else:
            self.r[dest] = val

    def _op_PRINT(self, instr):
        print(self.to_str(self.r[instr[1]]))

    def _op_HALT(self, instr):
        self.halted = True

    def _op_BREAKPOINT(self, instr):
        print(f"\n[调试] 断点 IP: {self.ip}")
        input("按 Enter 继续...")

    def _op_ASYNC_CALL(self, instr):
        # ASYNC_CALL dest, callee, arg_start, arg_count
        pass # To implement using ThreadPool

    def _op_AWAIT(self, instr):
        pass

    def _op_BATCH_OP(self, instr):
        pass


def run_file(path):
    vm = RegisterVM()
    vm.load_file(path)
    vm.run()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python -m zhiai.register_vm <文件.zab>", file=sys.stderr)
        sys.exit(1)
    run_file(sys.argv[1])
