# cython: language_level=3
"""致爱高速寄存器虚拟机 — Cython 编译加速实现 (v1.1.0 架构)"""

import json
import os
import sys

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
        if name in self.vars: return self.vars[name]
        if self.parent: return self.parent.get(name)
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
    def __init__(self, klass):
        self.klass = klass
        self.shape = EMPTY_SHAPE
        self.fields = []

    def get_prop(self, name):
        offset = self.shape.get_offset(name)
        if offset is not None: return self.fields[offset]
        if name in self.klass["methods"]: return self.klass["methods"][name]
        return None

    def set_prop(self, name, value):
        offset = self.shape.get_offset(name)
        if offset is not None: self.fields[offset] = value
        else:
            self.shape = self.shape.transition(name)
            self.fields.append(value)


class FastRegisterVM:
    """Cython 优化的基于寄存器的虚拟机"""

    def __init__(self):
        self.global_env = Environment()
        self.call_stack = []
        self.ip = 0
        self.instructions = []
        self.constants = []
        self.halted = False
        self.exception_handlers = []
        self.deferred = []
        self._top_r = [None] * 256
        self.gc = IncrementalGC(self)

        for name, func in BUILTINS.items():
            self.global_env.define(name, func)

        self.global_env.define("导入", self._builtin_import)
        self.global_env.define("垃圾回收", self.gc.collect)

    def _builtin_import(self, module_path):
        if not os.path.exists(module_path):
            if os.path.exists(module_path + ".zab"): module_path += ".zab"
            elif os.path.exists(module_path + ".za"): module_path += ".za"
            else: raise VMError(f"导入失败: 找不到模块 '{module_path}'")
                
        sub_vm = FastRegisterVM()
        
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
        if isinstance(bytecode, str): bytecode = json.loads(bytecode)
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

        cdef int ip = 0
        cdef list instructions = self.instructions
        cdef list constants = self.constants
        cdef int n_instr = len(instructions)
        cdef list instr
        cdef int op
        cdef list call_stack = self.call_stack
        cdef list r = self._top_r

        self.halted = False

        while ip < n_instr and not self.halted:
            try:
                instr = instructions[ip]
                op = <int>instr[0]
                ip += 1

                if op == 0: # LOAD_CONST
                    r[instr[1]] = constants[instr[2]]
                elif op == 1: # LOAD_GLOBAL
                    env = call_stack[-1].env if call_stack else self.global_env
                    r[instr[1]] = env.get(constants[instr[2]])
                elif op == 2: # STORE_GLOBAL
                    env = call_stack[-1].env if call_stack else self.global_env
                    env.set(constants[instr[1]], r[instr[2]])
                elif op == 3: # DEF_GLOBAL
                    env = call_stack[-1].env if call_stack else self.global_env
                    env.define(constants[instr[1]], r[instr[2]])
                elif op == 4: # MOVE
                    r[instr[1]] = r[instr[2]]
                elif op == 5: # LOAD_NULL
                    r[instr[1]] = None
                elif op == 6: # LOAD_BOOL
                    r[instr[1]] = True if instr[2] else False
                elif op == 7: # ADD
                    a = r[instr[2]]
                    b = r[instr[3]]
                    if isinstance(a, str) or isinstance(b, str):
                        a_str = "空" if a is None else ("真" if a is True else ("假" if a is False else str(a)))
                        b_str = "空" if b is None else ("真" if b is True else ("假" if b is False else str(b)))
                        r[instr[1]] = a_str + b_str
                    else: r[instr[1]] = a + b
                elif op == 8: # SUB
                    r[instr[1]] = r[instr[2]] - r[instr[3]]
                elif op == 9: # MUL
                    r[instr[1]] = r[instr[2]] * r[instr[3]]
                elif op == 10: # DIV
                    a = r[instr[2]]
                    b = r[instr[3]]
                    if b == 0: raise VMError("除以零")
                    if isinstance(a, int) and isinstance(b, int) and a % b == 0: r[instr[1]] = a // b
                    else: r[instr[1]] = a / b
                elif op == 11: # MOD
                    b = r[instr[3]]
                    if b == 0: raise VMError("除以零")
                    r[instr[1]] = r[instr[2]] % b
                elif op == 12: # POW
                    r[instr[1]] = r[instr[2]] ** r[instr[3]]
                elif op == 13: # EQ
                    r[instr[1]] = r[instr[2]] == r[instr[3]]
                elif op == 14: # NEQ
                    r[instr[1]] = r[instr[2]] != r[instr[3]]
                elif op == 15: # LT
                    r[instr[1]] = r[instr[2]] < r[instr[3]]
                elif op == 16: # GT
                    r[instr[1]] = r[instr[2]] > r[instr[3]]
                elif op == 17: # LTE
                    r[instr[1]] = r[instr[2]] <= r[instr[3]]
                elif op == 18: # GTE
                    r[instr[1]] = r[instr[2]] >= r[instr[3]]
                elif op == 19: # NEG
                    r[instr[1]] = -r[instr[2]]
                elif op == 20: # NOT
                    val = r[instr[2]]
                    truthy = False if val is None or val is False or val == 0 or val == "" or val == [] or val == {} else True
                    r[instr[1]] = not truthy
                elif op == 21: # LOAD_INDEX
                    obj = r[instr[2]]
                    idx_val = r[instr[3]]
                    if isinstance(obj, (list, str)):
                        idx = int(idx_val)
                        if idx < 0: idx += len(obj)
                        if idx < 0 or idx >= len(obj): raise VMError(f"索引越界: {idx}")
                        r[instr[1]] = obj[idx]
                    elif isinstance(obj, dict): r[instr[1]] = obj.get(idx_val)
                    else: raise VMError("无法索引非数组/对象")
                elif op == 22: # STORE_INDEX
                    obj = r[instr[1]]
                    idx_val = r[instr[2]]
                    val = r[instr[3]]
                    if isinstance(obj, list):
                        idx = int(idx_val)
                        if idx < 0: idx += len(obj)
                        if idx < 0 or idx >= len(obj): raise VMError(f"索引赋值越界: {idx}")
                        obj[idx] = val
                    elif isinstance(obj, dict): obj[idx_val] = val
                    else: raise VMError("无法索引赋值非数组/对象")
                elif op == 23: # LOAD_PROP
                    obj = r[instr[2]]
                    name = constants[instr[3]]
                    if isinstance(obj, Instance): r[instr[1]] = obj.get_prop(name)
                    elif isinstance(obj, dict): r[instr[1]] = obj.get(name)
                    elif isinstance(obj, str):
                        if name == "长度": r[instr[1]] = len(obj)
                        elif name in STRING_METHODS: r[instr[1]] = lambda *a: STRING_METHODS[name](obj, *a)
                        else: raise VMError(f"字符串没有方法: {name}")
                    elif isinstance(obj, list):
                        if name == "长度": r[instr[1]] = len(obj)
                        elif name in ARRAY_METHODS: r[instr[1]] = lambda *a: ARRAY_METHODS[name](obj, *a)
                        else: raise VMError(f"数组没有方法: {name}")
                    else: r[instr[1]] = getattr(obj, name, None)
                elif op == 24: # STORE_PROP
                    obj = r[instr[1]]
                    name = constants[instr[2]]
                    val = r[instr[3]]
                    if isinstance(obj, Instance): obj.set_prop(name, val)
                    elif isinstance(obj, dict): obj[name] = val
                    else: setattr(obj, name, val)
                elif op == 25: # JMP
                    ip = instr[1]
                elif op == 26: # JMP_IF
                    val = r[instr[1]]
                    truthy = False if val is None or val is False or val == 0 or val == "" or val == [] or val == {} else True
                    if truthy: ip = instr[2]
                elif op == 27: # JMP_IFNOT
                    val = r[instr[1]]
                    truthy = False if val is None or val is False or val == 0 or val == "" or val == [] or val == {} else True
                    if not truthy: ip = instr[2]
                elif op == 28: # CALL
                    dest = instr[1]
                    callee = r[instr[2]]
                    arg_start = instr[3]
                    arg_count = instr[4]
                    args = [r[arg_start + i] for i in range(arg_count)]
                    
                    if isinstance(callee, dict) and "type" in callee:
                        if callee["type"] == "class":
                            instance = Instance(callee)
                            if "构造" in callee["methods"]:
                                constructor = callee["methods"]["构造"]
                                env = Environment(constructor.get("closure", self.global_env))
                                env.define("这", instance)
                                for i, param in enumerate(constructor.get("params", [])):
                                    if i < len(args): env.define(param, args[i])
                                    else: env.define(param, None)
                                frame = Frame(constructor["instructions"], ip, env=env, constants=constants, return_reg=dest, is_constructor=True, instance=instance)
                                call_stack.append(frame)
                                instructions = constructor["instructions"]
                                constants = constructor.get("constants", [])
                                ip = constructor.get("entry_ip", 0)
                                n_instr = len(instructions)
                                r = frame.registers
                                continue
                            else:
                                r[dest] = instance
                                continue
                        elif callee["type"] == "function":
                            env = Environment(callee.get("closure", self.global_env))
                            for i, param in enumerate(callee.get("params", [])):
                                if i < len(args): env.define(param, args[i])
                                else: env.define(param, None)
                            frame = Frame(callee["instructions"], ip, env=env, constants=constants, return_reg=dest)
                            for i in range(len(args)): frame.registers[i] = args[i]
                            call_stack.append(frame)
                            instructions = callee["instructions"]
                            constants = callee.get("constants", [])
                            ip = callee.get("entry_ip", 0)
                            n_instr = len(instructions)
                            r = frame.registers
                            continue
                            
                    from zhiai.builtins import wrap_callable
                    r[dest] = wrap_callable(callee)(*args)
                elif op == 29: # CALL_METHOD
                    dest = instr[1]
                    obj = r[instr[2]]
                    method_name = constants[instr[3]]
                    arg_start = instr[4]
                    arg_count = instr[5]
                    args = [r[arg_start + i] for i in range(arg_count)]
                    
                    if isinstance(obj, Instance):
                        method = obj.klass["methods"].get(method_name)
                        if method is None: raise VMError(f"类没有方法 '{method_name}'")
                        env = Environment(method.get("closure", self.global_env))
                        env.define("这", obj)
                        for i, param in enumerate(method.get("params", [])):
                            if i < len(args): env.define(param, args[i])
                            else: env.define(param, None)
                        frame = Frame(method["instructions"], ip, env=env, constants=constants, return_reg=dest)
                        for i in range(len(args)): frame.registers[i] = args[i]
                        call_stack.append(frame)
                        instructions = method["instructions"]
                        constants = method.get("constants", [])
                        ip = method.get("entry_ip", 0)
                        n_instr = len(instructions)
                        r = frame.registers
                        continue
                    elif isinstance(obj, list) and method_name in ARRAY_METHODS:
                        r[dest] = ARRAY_METHODS[method_name](obj, *args)
                        continue
                    elif isinstance(obj, str) and method_name in STRING_METHODS:
                        r[dest] = STRING_METHODS[method_name](obj, *args)
                        continue
                        
                    method = getattr(obj, method_name, None)
                    if callable(method): r[dest] = method(*args)
                    else: raise VMError(f"类型无法调用方法 '{method_name}'")
                elif op == 30: # RET
                    ret_val = r[instr[1]]
                    if not call_stack:
                        self.halted = True
                        r[0] = ret_val
                        continue
                    frame = call_stack.pop()
                    if frame.deferred:
                        for cb in reversed(frame.deferred):
                            try: self.call_function_nested(cb, [])
                            except: pass
                    instructions = frame.instructions
                    constants = frame.constants
                    ip = frame.return_addr
                    n_instr = len(instructions)
                    
                    if call_stack: r = call_stack[-1].registers
                    else: r = self._top_r
                    
                    if frame.is_constructor: r[frame.return_reg] = frame.instance
                    else:
                        if frame.return_reg is not None: r[frame.return_reg] = ret_val
                elif op == 31: # MAKE_FUNC
                    dest = instr[1]
                    name_idx = instr[2]
                    arity = instr[3]
                    param_count = instr[4]
                    param_start = instr[5]
                    entry_ip = instr[6]
                    name = constants[name_idx]
                    params = [constants[param_start + i] for i in range(param_count)]
                    env = call_stack[-1].env if call_stack else self.global_env
                    func = {"type": "function", "name": name, "arity": arity, "params": params, "entry_ip": entry_ip, "instructions": instructions, "constants": constants, "closure": env}
                    env.define(name, func)
                    r[dest] = func
                elif op == 32: # MAKE_ARRAY
                    dest = instr[1]
                    start = instr[2]
                    count = instr[3]
                    r[dest] = [r[start + i] for i in range(count)]
                elif op == 33: # MAKE_OBJECT
                    dest = instr[1]
                    start = instr[2]
                    count = instr[3]
                    obj = {}
                    for i in range(count):
                        key = r[start + i * 2]
                        val = r[start + i * 2 + 1]
                        obj[key] = val
                    r[dest] = obj
                elif op == 34: # MAKE_CLASS
                    dest = instr[1]
                    name = constants[instr[2]]
                    methods = r[instr[3]]
                    klass = {"type": "class", "name": name, "methods": methods}
                    env = call_stack[-1].env if call_stack else self.global_env
                    env.define(name, klass)
                    r[dest] = klass
                elif op == 35: # NEW
                    dest = instr[1]
                    klass = r[instr[2]]
                    instance = Instance(klass)
                    r[dest] = instance
                elif op == 36: # TRY
                    handler_ip = instr[1]
                    catch_reg = instr[2]
                    if call_stack: call_stack[-1].exception_handlers.append((handler_ip, catch_reg))
                    else: self.exception_handlers.append((handler_ip, catch_reg))
                elif op == 37: # END_TRY
                    if call_stack:
                        if call_stack[-1].exception_handlers: call_stack[-1].exception_handlers.pop()
                    else:
                        if self.exception_handlers: self.exception_handlers.pop()
                elif op == 38: # RAISE
                    raise VMError(str(r[instr[1]]))
                elif op == 39: # TRY_PROPAGATE
                    dest = instr[1]
                    src = instr[2]
                    val = r[src]
                    if hasattr(val, "是失败") and val.是失败():
                        # Inline RET
                        ret_val = val
                        if not call_stack:
                            self.halted = True
                            r[0] = ret_val
                            continue
                        frame = call_stack.pop()
                        instructions = frame.instructions
                        constants = frame.constants
                        ip = frame.return_addr
                        n_instr = len(instructions)
                        if call_stack: r = call_stack[-1].registers
                        else: r = self._top_r
                        if frame.is_constructor: r[frame.return_reg] = frame.instance
                        else:
                            if frame.return_reg is not None: r[frame.return_reg] = ret_val
                        continue
                    if hasattr(val, "是空") and val.是空():
                        ret_val = val
                        if not call_stack:
                            self.halted = True
                            r[0] = ret_val
                            continue
                        frame = call_stack.pop()
                        instructions = frame.instructions
                        constants = frame.constants
                        ip = frame.return_addr
                        n_instr = len(instructions)
                        if call_stack: r = call_stack[-1].registers
                        else: r = self._top_r
                        if frame.is_constructor: r[frame.return_reg] = frame.instance
                        else:
                            if frame.return_reg is not None: r[frame.return_reg] = ret_val
                        continue
                    if hasattr(val, "获取"): r[dest] = val.获取()
                    else: r[dest] = val
                elif op == 40: # PRINT
                    val = r[instr[1]]
                    val_str = "空" if val is None else ("真" if val is True else ("假" if val is False else str(val)))
                    print(val_str)
                elif op == 41: # HALT
                    self.halted = True
            except Exception as e:
                if call_stack:
                    frame = call_stack[-1]
                    if frame.exception_handlers:
                        handler_ip, catch_reg = frame.exception_handlers.pop()
                        frame.registers[catch_reg] = str(e)
                        ip = handler_ip
                        continue
                else:
                    if self.exception_handlers:
                        handler_ip, catch_reg = self.exception_handlers.pop()
                        r[catch_reg] = str(e)
                        ip = handler_ip
                        continue
                
                if call_stack:
                    frame = call_stack.pop()
                    if frame.deferred:
                        for cb in reversed(frame.deferred):
                            try: self.call_function_nested(cb, [])
                            except: pass
                    if call_stack:
                        last_frame = call_stack[-1]
                        instructions = last_frame.instructions
                        constants = last_frame.constants
                        ip = last_frame.return_addr
                        n_instr = len(instructions)
                        r = last_frame.registers
                        raise e # re-raise to be caught in the outer while block
                        
                print(f"致命错误: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                self.halted = True
                
        self.ip = ip
        if self.deferred:
            for cb in reversed(self.deferred):
                try: self.call_function_nested(cb, [])
                except: pass
        builtins.CURRENT_VM = old_vm

# Allow easy alias export
VM = FastRegisterVM
