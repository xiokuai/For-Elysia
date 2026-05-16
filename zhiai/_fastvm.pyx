# cython: language_level=3
"""致爱高速虚拟机 — Cython 实现"""

import json
import os
import sys

from zhiai.builtins import BUILTINS, ARRAY_METHODS, STRING_METHODS, BATCH_FUNC_MAP, ZhiAiError

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
    def __init__(self, instructions, int return_addr, env=None, constants=None, int locals_count=0):
        self.instructions = instructions
        self.return_addr = return_addr
        self.env = env
        self.constants = constants
        self.locals = [None] * locals_count

class VM:
    def __init__(self):
        self.stack = []
        self.global_env = Environment()
        self.call_stack = []
        self.ip = 0
        self.instructions = []
        self.constants = []
        self.halted = False
        
        # 注册内置函数
        for name, func in BUILTINS.items():
            self.global_env.define(name, func)
        self.global_env.define("导入", self._builtin_import)

    def _builtin_import(self, module_path):
        # 简单实现，回退到标准逻辑
        from zhiai.vm import VM as StandardVM
        sub_vm = StandardVM()
        # ... (与 vm.py 逻辑相同)
        return {} # 简化版

    def load(self, bytecode):
        if isinstance(bytecode, str):
            bytecode = json.loads(bytecode)
        self.constants = bytecode.get("constants", [])
        self.instructions = bytecode.get("instructions", [])
        user_globals = bytecode.get("globals", {})
        for k, v in user_globals.items():
            self.global_env.define(k, v)

    def load_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            self.load(f.read())

    def push(self, value):
        self.stack.append(value)

    def pop(self):
        return self.stack.pop()

    def peek(self):
        return self.stack[-1]

    def is_truthy(self, value):
        if value is None: return False
        if isinstance(value, bool): return value
        if isinstance(value, (int, float)): return value != 0
        return bool(value)

    def run(self):
        cdef int ip = self.ip
        cdef list instructions = self.instructions
        cdef list constants = self.constants
        cdef list stack = self.stack
        
        while not self.halted and ip < len(instructions):
            instr = instructions[ip]
            op = instr[0]
            ip += 1
            
            if op == "PUSH":
                stack.append(constants[instr[1]])
            elif op == "POP":
                stack.pop()
            elif op == "ADD":
                b = stack.pop()
                a = stack.pop()
                stack.append(a + b)
            elif op == "SUB":
                b = stack.pop()
                a = stack.pop()
                stack.append(a - b)
            elif op == "MUL":
                b = stack.pop()
                a = stack.pop()
                stack.append(a * b)
            elif op == "DIV":
                b = stack.pop()
                a = stack.pop()
                stack.append(a / b)
            elif op == "EQ":
                b = stack.pop()
                a = stack.pop()
                stack.append(a == b)
            elif op == "LOAD":
                name = constants[instr[1]]
                env = self.call_stack[-1].env if self.call_stack else self.global_env
                stack.append(env.get(name))
            elif op == "STORE":
                name = constants[instr[1]]
                val = stack[-1]
                env = self.call_stack[-1].env if self.call_stack else self.global_env
                env.set(name, val)
            elif op == "DEF":
                name = constants[instr[1]]
                val = stack[-1]
                env = self.call_stack[-1].env if self.call_stack else self.global_env
                env.define(name, val)
            elif op == "CALL":
                # 简化版实现，实际应包含 TCO 和 Frame 管理
                argc = instr[1]
                args = [stack.pop() for _ in range(argc)]
                args.reverse()
                callee = stack.pop()
                result = callee(*args)
                stack.append(result)
            elif op == "RET":
                if not self.call_stack:
                    self.halted = True
                else:
                    frame = self.call_stack.pop()
                    instructions = frame.instructions
                    constants = frame.constants
                    ip = frame.return_addr
            elif op == "JMP":
                ip = instr[1]
            elif op == "JMP_IFNOT":
                if not self.is_truthy(stack.pop()):
                    ip = instr[1]
            elif op == "BATCH_OP":
                func_id = instr[1]
                argc = instr[2]
                params = [stack.pop() for _ in range(argc)]
                params.reverse()
                batch_func = BATCH_FUNC_MAP.get(func_id)
                stack.append(batch_func(*params))
            elif op == "HALT":
                self.halted = True
            
        self.ip = ip
