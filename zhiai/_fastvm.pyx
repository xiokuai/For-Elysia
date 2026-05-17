# cython: language_level=3
"""致爱高速虚拟机 — Cython 编译加速实现"""

import json
import os
import sys

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
        self.locals = [None] * locals_count
        self.locals_count = locals_count
        self.exception_handlers = []
        self.deferred = []
        self.is_constructor = is_constructor
        self.instance = instance


class Instance:
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
    def __init__(self):
        self.stack = []
        self.global_env = Environment()
        self.call_stack = []
        self.ip = 0
        self.instructions = []
        self.constants = []
        self.halted = False
        self.gc = MarkSweepGC(self)
        self.deferred = []

        # 注册内置
        for name, func in BUILTINS.items():
            self.global_env.define(name, func)
        self.global_env.define("导入", self._builtin_import)
        self.global_env.define("垃圾回收", self.gc.collect)

    def _builtin_import(self, module_path):
        if not os.path.exists(module_path):
            if os.path.exists(module_path + ".zab"): module_path += ".zab"
            elif os.path.exists(module_path + ".za"): module_path += ".za"
            else: raise VMError(f"导入失败: 找不到模块 '{module_path}'")
        sub_vm = VM()
        sub_vm.load_file(module_path)
        sub_vm.run()
        exports = {}
        for k, v in sub_vm.global_env.vars.items():
            if k not in BUILTINS and k != "导入":
                exports[k] = v
        return exports

    def load_file(self, path):
        with open(path, "rb") as f:
            header = f.read(4)
            if header == b"ZAB\x00":
                import marshal
                bytecode = marshal.load(f)
            else:
                f.seek(0)
                bytecode = json.loads(f.read().decode("utf-8"))
        
        self.constants = bytecode.get("constants", [])
        loaded_instrs = bytecode.get("instructions", [])
        self.instructions = []
        for instr in loaded_instrs:
            if isinstance(instr[0], str):
                op_int = OPCODE_MAP.get(instr[0], 0)
                self.instructions.append([op_int] + list(instr[1:]))
            else:
                self.instructions.append(instr)
        
        user_globals = bytecode.get("globals", {})
        for k, v in user_globals.items():
            self.global_env.define(k, v)

    def push(self, val):
        self.stack.append(val)

    def pop(self):
        return self.stack.pop()

    def to_str(self, value):
        if value is None: return "空"
        if isinstance(value, bool): return "真" if value else "假"
        if isinstance(value, float):
            if value != value: return "NaN"
            if value == float('inf'): return "Infinity"
            if value == float('-inf'): return "-Infinity"
            if value == int(value): return str(int(value))
        return str(value)

    def is_truthy(self, value):
        if value is None: return False
        if isinstance(value, bool): return value
        if isinstance(value, (int, float)): return value != 0
        if isinstance(value, (str, list, dict)): return len(value) > 0
        return True

    def call_function_nested(self, func, args):
        # 简化版嵌套调用，不改变主 VM 状态
        from zhiai.builtins import wrap_callable
        wrapped = wrap_callable(func)
        return wrapped(*args)

    def run(self):
        import zhiai.builtins as builtins
        builtins.CURRENT_VM = self
        
        cdef int ip = 0
        cdef list instructions = self.instructions
        cdef list constants = self.constants
        cdef list stack = self.stack
        cdef int n_instr = len(instructions)
        cdef list instr
        cdef int op
        
        while ip < n_instr and not self.halted:
            instr = instructions[ip]
            op = <int>instr[0]
            ip += 1
            
            if op == 0: # PUSH
                stack.append(constants[<int>instr[1]])
            elif op == 1: # POP
                stack.pop()
            elif op == 2: # DUP
                stack.append(stack[-1])
            elif op == 3 or op == 50: # ADD or BINOP '+'
                b = stack.pop(); a = stack.pop()
                if isinstance(a, str) or isinstance(b, str):
                    stack.append(self.to_str(a) + self.to_str(b))
                else: stack.append(a + b)
            elif op == 4: # SUB
                b = stack.pop(); a = stack.pop()
                stack.append(a - b)
            elif op == 5: # MUL
                b = stack.pop(); a = stack.pop()
                stack.append(a * b)
            elif op == 6: # DIV
                b = stack.pop(); a = stack.pop()
                if b == 0: raise VMError("除以零")
                if isinstance(a, int) and isinstance(b, int) and a % b == 0:
                    stack.append(a // b)
                else: stack.append(a / b)
            elif op == 22: # LOAD_INDEX
                idx_val = stack.pop(); obj = stack.pop()
                if isinstance(obj, (list, str)):
                    idx = int(idx_val)
                    if idx < 0: idx += len(obj)
                    if idx < 0 or idx >= len(obj): raise VMError(f"索引越界: {idx}")
                    stack.append(obj[idx])
                elif isinstance(obj, dict): stack.append(obj.get(idx_val))
                else: raise VMError("无法索引非数组/对象")
            elif op == 23: # STORE_INDEX
                idx_val = stack.pop(); obj = stack.pop(); val = stack.pop()
                if isinstance(obj, list):
                    idx = int(idx_val)
                    if idx < 0: idx += len(obj)
                    if idx < 0 or idx >= len(obj): raise VMError(f"索引赋值越界: {idx}")
                    obj[idx] = val
                elif isinstance(obj, dict): obj[idx_val] = val
                stack.append(val)
            elif op == 26: # CALL
                argc = <int>instr[1]
                args = [stack.pop() for _ in range(argc)]
                args.reverse()
                callee = stack.pop()
                
                # JIT Trigger Logic (Bug #20)
                if isinstance(callee, dict) and callee.get("type") == "function":
                    callee["jit_count"] = callee.get("jit_count", 0) + 1
                    if callee["jit_count"] > 15 and callee.get("jitted_func") is None:
                        from zhiai.vm_jit import compile_function
                        callee["jitted_func"] = compile_function(callee, self.global_env)
                    if callee.get("jitted_func"):
                        l_cnt = callee.get("locals_count", 0)
                        l_list = args + [None] * (l_cnt - len(args))
                        stack.append(callee["jitted_func"](l_list, self.global_env))
                        continue

                from zhiai.builtins import wrap_callable
                res = wrap_callable(callee)(*args)
                stack.append(res)
            elif op == 32: # BATCH_OP
                func_id = <int>instr[1]
                arg_cnt = <int>instr[2]
                params = [stack.pop() for _ in range(arg_cnt)]
                params.reverse()
                batch_func = BATCH_FUNC_MAP.get(func_id)
                stack.append(batch_func(*params))
            elif op == 40: # NEW
                klass = stack.pop()
                inst = Instance(klass)
                self.gc.track(inst)
                if "构造" in klass["methods"]:
                    # Cython 简化版 ctor 调用：直接回退到 Python CALL 逻辑
                    from zhiai.builtins import wrap_callable
                    ctor = klass["methods"]["构造"]
                    # 这里假设后续会有一个 CALL 指令，或者直接在这里处理
                    # 为了安全，我们先只创建实例，构造函数由编译器生成的后续 CALL 处理
                    stack.append(inst)
                else:
                    stack.append(inst)
            elif op == 31: # HALT
                self.halted = True
            
        self.ip = ip
        if self.deferred:
            for cb in reversed(self.deferred):
                try: self.call_function_nested(cb, [])
                except: pass
