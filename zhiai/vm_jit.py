# -*- coding: utf-8 -*-
"""致爱方法级 JIT 编译器 (Method JIT Compiler - 3AC/SSA Optimized)"""

import sys
from zhiai.vm import OPCODE_LIST
from zhiai.cfg import CFG
from zhiai.ssa import SSABuilder

def compile_function(func_obj, global_env):
    """动态将致爱字节码函数 JIT 编译为高效的三地址码 (3AC) 形式的原生 Python 代码"""
    instructions = func_obj["instructions"]
    constants = func_obj["constants"]
    
    # 1. 静态栈深度分析 (Static Stack Depth Analysis) - 迈向 SSA 的基石
    depths = [None] * len(instructions)
    def simulate(ip, d):
        while ip < len(instructions):
            if depths[ip] is not None:
                return depths[ip] == d
            depths[ip] = d
            op_int = instructions[ip][0]
            op_name = OPCODE_LIST[op_int] if op_int < len(OPCODE_LIST) else str(op_int)
            
            if op_name in ("PUSH", "LOAD_LOCAL", "LOAD", "LOAD_GLOBAL", "LOAD_INDEX", "LOAD_PROP", "NEW"):
                d += 1
            elif op_name in ("POP", "STORE_LOCAL", "STORE", "STORE_GLOBAL", "PRINT", "RAISE", "JMP_IF", "JMP_IFNOT", "NOT"):
                d -= 1
            elif op_name in ("ADD", "FAST_ADD", "SUB", "FAST_SUB", "MUL", "DIV", "MOD", "POW", "EQ", "NEQ", "LT", "GT", "LTE", "GTE", "AND", "OR", "BINOP"):
                d -= 1 
            elif op_name in ("STORE_INDEX", "STORE_PROP"):
                d -= 2 
            elif op_name == "CALL":
                d = d - instructions[ip][1] - 1 + 1
            elif op_name == "CALL_METHOD":
                d = d - instructions[ip][2] - 1 + 1
            elif op_name in ("MAKE_ARRAY", "MAKE_OBJECT"):
                argc = instructions[ip][1]
                if op_name == "MAKE_OBJECT": argc *= 2
                d = d - argc + 1
            elif op_name == "JMP":
                return simulate(instructions[ip][1], d)
            
            if op_name in ("JMP_IF", "JMP_IFNOT", "TRY"):
                if not simulate(instructions[ip][1], d): return False
            elif op_name == "RET":
                return True
                
            ip += 1
        return True

    # 尝试进行栈模拟
    if not simulate(0, 0):
        return None # 如果模拟失败，回退到解释执行
        
    # 2. 构建 CFG 与 SSA (静态单赋值) 架构分析
    cfg = CFG(instructions)
    cfg.build()
    
    # 收集所有的局部变量赋值，找出对应的定义块
    local_defs = {}
    if cfg.blocks:
        for block in cfg.blocks.values():
            for instr in block.instructions:
                op_int = instr[0]
                op_name = OPCODE_LIST[op_int] if op_int < len(OPCODE_LIST) else str(op_int)
                if op_name == "STORE_LOCAL":
                    local_idx = instr[1]
                    var_name = f"local_{local_idx}"
                    if var_name not in local_defs:
                        local_defs[var_name] = set()
                    local_defs[var_name].add(block)
                    
        # 运行 SSA 构建器放置 Phi 节点
        ssa_builder = SSABuilder(cfg)
        ssa_builder.build()
        for var_name, def_blocks in local_defs.items():
            ssa_builder.insert_phi_for_var(var_name, def_blocks)

    code = []
    code.append("def jitted_func(locals_, global_env):")
    code.append("    # 3-Address Code 虚拟寄存器组 & 预分配 SSA 节点")
    code.append("    r = [None] * 256")
    code.append(f"    ip = {func_obj['entry_ip']}")
    code.append("    n_instr = len(instructions)")
    code.append("    while ip < n_instr:")
    
    for i, instr in enumerate(instructions):
        d = depths[i]
        
        # Phi Node Comment Output
        if cfg.blocks and i in cfg.blocks:
            block = cfg.blocks[i]
            if block in ssa_builder.phi_nodes:
                for var_name in ssa_builder.phi_nodes[block]:
                    pred_labels = [f"B{p.start_ip}" for p in block.predecessors]
                    code.append(f"        # Phi Node: {var_name} = Φ({', '.join(pred_labels)})")

        if d is None:
            # 遇到无法到达的死代码，直接跳过
            code.append(f"        if ip == {i}:")
            code.append("            ip += 1; continue")
            continue
            
        code.append(f"        if ip == {i}:")
        op_int = instr[0]
        op_name = OPCODE_LIST[op_int] if op_int < len(OPCODE_LIST) else str(op_int)
        
        # 将原有的栈操作直接转译为确定的寄存器索引 (3AC)
        if op_name == "PUSH":
            code.append(f"            r[{d}] = constants[{instr[1]}]")
            code.append("            ip += 1")
        elif op_name == "POP":
            code.append("            ip += 1")
        elif op_name == "DUP":
            code.append(f"            r[{d}] = r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "LOAD_LOCAL":
            idx = instr[1]
            code.append(f"            if {idx} < len(locals_): r[{d}] = locals_[{idx}]")
            code.append(f"            else: r[{d}] = None")
            code.append("            ip += 1")
        elif op_name == "STORE_LOCAL":
            idx = instr[1]
            code.append(f"            if {idx} < len(locals_): locals_[{idx}] = r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "LOAD":
            code.append(f"            r[{d}] = global_env.get(constants[{instr[1]}])")
            code.append("            ip += 1")
        elif op_name == "STORE":
            code.append(f"            global_env.define(constants[{instr[1]}], r[{d-1}])")
            code.append("            ip += 1")
        elif op_name in ("ADD", "FAST_ADD"):
            code.append(f"            a, b = r[{d-2}], r[{d-1}]")
            code.append("            if isinstance(a, str) or isinstance(b, str):")
            code.append("                from zhiai.builtins import _转换文字")
            code.append(f"                r[{d-2}] = _转换文字(a) + _转换文字(b)")
            code.append(f"            else: r[{d-2}] = a + b")
            code.append("            ip += 1")
        elif op_name in ("SUB", "FAST_SUB"):
            code.append(f"            r[{d-2}] = r[{d-2}] - r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "MUL":
            code.append(f"            r[{d-2}] = r[{d-2}] * r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "DIV":
            code.append(f"            a, b = r[{d-2}], r[{d-1}]")
            code.append("            if b == 0: return None")
            code.append("            if isinstance(a, int) and isinstance(b, int) and a % b == 0:")
            code.append(f"                r[{d-2}] = a // b")
            code.append(f"            else: r[{d-2}] = a / b")
            code.append("            ip += 1")
        elif op_name == "EQ":
            code.append(f"            r[{d-2}] = r[{d-2}] == r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "NEQ":
            code.append(f"            r[{d-2}] = r[{d-2}] != r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "LT":
            code.append(f"            r[{d-2}] = r[{d-2}] < r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "GT":
            code.append(f"            r[{d-2}] = r[{d-2}] > r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "LTE":
            code.append(f"            r[{d-2}] = r[{d-2}] <= r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "GTE":
            code.append(f"            r[{d-2}] = r[{d-2}] >= r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "RET":
            code.append(f"            return r[{d-1}]")
        elif op_name == "JMP":
            code.append(f"            ip = {instr[1]}")
        elif op_name == "JMP_IF":
            code.append(f"            if r[{d-1}]:")
            code.append(f"                ip = {instr[1]}")
            code.append("            else:")
            code.append("                ip += 1")
        elif op_name == "JMP_IFNOT":
            code.append(f"            if not r[{d-1}]:")
            code.append(f"                ip = {instr[1]}")
            code.append("            else:")
            code.append("                ip += 1")
        elif op_name == "CALL":
            argc = instr[1]
            code.append(f"            callee = r[{d - argc - 1}]")
            code.append(f"            func_args = r[{d - argc}:{d}]")
            code.append("            if isinstance(callee, dict) and 'jitted_func' in callee and callee['jitted_func'] is not None:")
            code.append("                l_list = func_args + [None] * (callee.get('locals_count', 0) - len(func_args))")
            code.append(f"                r[{d - argc - 1}] = callee['jitted_func'](l_list, global_env)")
            code.append("            elif isinstance(callee, dict): return None # 动态回退")
            code.append("            else:")
            code.append("                from zhiai.builtins import wrap_callable")
            code.append("                wrapped = wrap_callable(callee)")
            code.append(f"                r[{d - argc - 1}] = wrapped(*func_args)")
            code.append("            ip += 1")
        elif op_name == "LOAD_PROP":
            code.append(f"            obj = r[{d-1}]")
            code.append(f"            name = constants[{instr[1]}]")
            code.append("            if hasattr(obj, 'get_prop'):")
            code.append(f"                r[{d-1}] = obj.get_prop(name)")
            code.append("            elif isinstance(obj, dict):")
            code.append(f"                r[{d-1}] = obj.get(name)")
            code.append("            else:")
            code.append(f"                r[{d-1}] = getattr(obj, name, None)")
            code.append("            ip += 1")
            
    code.append("    return None")
    
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
        return None
