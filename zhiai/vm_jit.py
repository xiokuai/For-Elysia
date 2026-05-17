# -*- coding: utf-8 -*-
"""致爱方法级 JIT 编译器 (Method JIT Compiler)"""

import sys
from zhiai.vm import OPCODE_LIST

def compile_function(func_obj, global_env):
    """动态将致爱字节码函数 JIT 编译为高效的 Python 原生可执行代码"""
    instructions = func_obj["instructions"]
    constants = func_obj["constants"]
    
    # 扫描所有的跳转目标
    jump_targets = {0}
    for instr in instructions:
        op_int = instr[0]
        op_name = OPCODE_LIST[op_int] if op_int < len(OPCODE_LIST) else str(op_int)
        if op_name in ("JMP", "JMP_IF", "JMP_IFNOT"):
            jump_targets.add(instr[1])
            
    code = []
    code.append("def jitted_func(locals_, global_env):")
    code.append("    stack = []")
    code.append(f"    ip = {func_obj['entry_ip']}")
    code.append("    n_instr = len(instructions)")
    code.append("    while ip < n_instr:")
    
    # 我们采用高效的基础块分发或 ip 直译
    for i, instr in enumerate(instructions):
        code.append(f"        if ip == {i}:")
        op_int = instr[0]
        op_name = OPCODE_LIST[op_int] if op_int < len(OPCODE_LIST) else str(op_int)
        
        # 逐个指令翻译为极其精简的 Python 原生操作
        if op_name == "PUSH":
            code.append(f"            stack.append(constants[{instr[1]}])")
            code.append("            ip += 1")
        elif op_name == "POP":
            code.append("            stack.pop()")
            code.append("            ip += 1")
        elif op_name == "DUP":
            code.append("            stack.append(stack[-1])")
            code.append("            ip += 1")
        elif op_name == "LOAD_LOCAL":
            code.append(f"            stack.append(locals_[{instr[1]}])")
            code.append("            ip += 1")
        elif op_name == "STORE_LOCAL":
            code.append(f"            locals_[{instr[1]}] = stack[-1]")
            code.append("            ip += 1")
        elif op_name == "LOAD":
            code.append(f"            stack.append(global_env.get(constants[{instr[1]}]))")
            code.append("            ip += 1")
        elif op_name == "STORE":
            code.append(f"            global_env.define(constants[{instr[1]}], stack[-1])")
            code.append("            ip += 1")
        elif op_name == "ADD" or op_name == "FAST_ADD":
            code.append("            b = stack.pop(); a = stack.pop()")
            code.append("            stack.append(a + b)")
            code.append("            ip += 1")
        elif op_name == "SUB" or op_name == "FAST_SUB":
            code.append("            b = stack.pop(); a = stack.pop()")
            code.append("            stack.append(a - b)")
            code.append("            ip += 1")
        elif op_name == "MUL":
            code.append("            b = stack.pop(); a = stack.pop()")
            code.append("            stack.append(a * b)")
            code.append("            ip += 1")
        elif op_name == "DIV":
            code.append("            b = stack.pop(); a = stack.pop()")
            code.append("            stack.append(a / b)")
            code.append("            ip += 1")
        elif op_name == "EQ":
            code.append("            b = stack.pop(); a = stack.pop()")
            code.append("            stack.append(a == b)")
            code.append("            ip += 1")
        elif op_name == "NEQ":
            code.append("            b = stack.pop(); a = stack.pop()")
            code.append("            stack.append(a != b)")
            code.append("            ip += 1")
        elif op_name == "LT":
            code.append("            b = stack.pop(); a = stack.pop()")
            code.append("            stack.append(a < b)")
            code.append("            ip += 1")
        elif op_name == "GT":
            code.append("            b = stack.pop(); a = stack.pop()")
            code.append("            stack.append(a > b)")
            code.append("            ip += 1")
        elif op_name == "LTE":
            code.append("            b = stack.pop(); a = stack.pop()")
            code.append("            stack.append(a <= b)")
            code.append("            ip += 1")
        elif op_name == "GTE":
            code.append("            b = stack.pop(); a = stack.pop()")
            code.append("            stack.append(a >= b)")
            code.append("            ip += 1")
        elif op_name == "BINOP":
            op = instr[1]
            code.append("            b = stack.pop(); a = stack.pop()")
            if op == '+':
                code.append("            stack.append(a + b)")
            elif op == '-':
                code.append("            stack.append(a - b)")
            elif op == '*':
                code.append("            stack.append(a * b)")
            elif op == '/':
                code.append("            stack.append(a / b)")
            elif op == '==':
                code.append("            stack.append(a == b)")
            elif op == '!=':
                code.append("            stack.append(a != b)")
            elif op == '<':
                code.append("            stack.append(a < b)")
            elif op == '>':
                code.append("            stack.append(a > b)")
            elif op == '<=':
                code.append("            stack.append(a <= b)")
            elif op == '>=':
                code.append("            stack.append(a >= b)")
            code.append("            ip += 1")
        elif op_name == "RET":
            code.append("            return stack.pop()")
        elif op_name == "JMP":
            code.append(f"            ip = {instr[1]}")
        elif op_name == "JMP_IF":
            code.append("            cond = stack.pop()")
            code.append("            if cond:")
            code.append(f"                ip = {instr[1]}")
            code.append("            else:")
            code.append("                ip += 1")
        elif op_name == "JMP_IFNOT":
            code.append("            cond = stack.pop()")
            code.append("            if not cond:")
            code.append(f"                ip = {instr[1]}")
            code.append("            else:")
            code.append("                ip += 1")
        elif op_name == "CALL":
            code.append(f"            argc = {instr[1]}")
            code.append("            func_args = [stack.pop() for _ in range(argc)]")
            code.append("            func_args.reverse()")
            code.append("            callee = stack.pop()")
            code.append("            # 回调处理，如果callee是JIT函数可以直接调用")
            code.append("            if isinstance(callee, dict) and 'jitted_func' in callee and callee['jitted_func'] is not None:")
            code.append("                j_func = callee['jitted_func']")
            code.append("                locals_count = callee.get('locals_count', 0)")
            code.append("                l_list = func_args + [None] * (locals_count - len(func_args))")
            code.append("                stack.append(j_func(l_list, global_env))")
            code.append("            elif isinstance(callee, dict) and callee.get('type') == 'function':")
            # 嵌套解释调用非 JIT 闭包
            code.append("                from zhiai.builtins import wrap_callable")
            code.append("                wrapped = wrap_callable(callee)")
            code.append("                stack.append(wrapped(*func_args))")
            code.append("            else:")
            code.append("                stack.append(callee(*func_args))")
            code.append("            ip += 1")
        elif op_name == "LOAD_PROP":
            code.append(f"            name = constants[{instr[1]}]")
            code.append("            obj = stack.pop()")
            code.append("            if isinstance(obj, dict):")
            code.append("                stack.append(obj.get(name))")
            code.append("            elif hasattr(obj, 'fields') and hasattr(obj, 'shape'):")
            code.append("                offset = obj.shape.get_offset(name)")
            code.append("                if offset is not None:")
            code.append("                    stack.append(obj.fields[offset])")
            code.append("                elif name in obj.klass['methods']:")
            code.append("                    stack.append(obj.klass['methods'][name])")
            code.append("                else:")
            code.append("                    stack.append(None)")
            code.append("            else:")
            code.append("                stack.append(getattr(obj, name, None))")
            code.append("            ip += 1")
        elif op_name == "STORE_PROP":
            code.append(f"            name = constants[{instr[1]}]")
            code.append("            obj = stack.pop()")
            code.append("            val = stack.pop()")
            code.append("            if isinstance(obj, dict):")
            code.append("                obj[name] = val")
            code.append("            elif hasattr(obj, 'fields') and hasattr(obj, 'shape'):")
            code.append("                offset = obj.shape.get_offset(name)")
            code.append("                if offset is not None:")
            code.append("                    obj.fields[offset] = val")
            code.append("                else:")
            code.append("                    new_shape = obj.shape.transition(name)")
            code.append("                    obj.shape = new_shape")
            code.append("                    obj.fields.append(val)")
            code.append("            else:")
            code.append("                setattr(obj, name, val)")
            code.append("            ip += 1")
        else:
            # 对于复杂指令，由于有 global_env，可以在 JIT 中生成回退解释逻辑
            code.append(f"            # 复杂指令 {op_name} 占位")
            code.append("            ip += 1")
            
    code.append("    return None")
    
    # 动态编译函数源码
    source = "\n".join(code)
    context = {
        "constants": constants,
        "instructions": instructions,
        "func_obj": func_obj,
    }
    try:
        exec(source, context)
        return context["jitted_func"]
    except Exception as e:
        # 编译失败则回退到解释执行，以确保高健壮性
        return None
