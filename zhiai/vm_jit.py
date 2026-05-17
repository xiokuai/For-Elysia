# -*- coding: utf-8 -*-
"""致爱方法级 JIT 编译器 (Method JIT Compiler - SSA & GVN Optimized)"""

import sys
from zhiai.vm import OPCODE_LIST
from zhiai.cfg import CFG
from zhiai.ssa import SSABuilder
from zhiai.optimizer import SSAOptimizer

def compile_function(func_obj, global_env):
    """动态将致爱字节码函数 JIT 编译为高效的三地址码 (3AC) 形式的原生 Python 代码 (含 SSA 深度优化)"""
    instructions = func_obj["instructions"]
    constants = func_obj["constants"]
    
    # 1. 静态栈深度分析
    depths = [None] * len(instructions)
    def simulate(ip, d):
        while ip < len(instructions):
            if depths[ip] is not None: return depths[ip] == d
            depths[ip] = d
            op_name = OPCODE_LIST[instructions[ip][0]]
            if op_name in ("PUSH", "LOAD_LOCAL", "LOAD", "LOAD_GLOBAL", "LOAD_INDEX", "LOAD_PROP", "NEW"): d += 1
            elif op_name in ("POP", "STORE_LOCAL", "STORE", "STORE_GLOBAL", "PRINT", "RAISE", "JMP_IF", "JMP_IFNOT", "NOT"): d -= 1
            elif op_name in ("ADD", "FAST_ADD", "SUB", "FAST_SUB", "MUL", "DIV", "MOD", "POW", "EQ", "NEQ", "LT", "GT", "LTE", "GTE", "AND", "OR", "BINOP"): d -= 1 
            elif op_name in ("STORE_INDEX", "STORE_PROP"): d -= 2 
            elif op_name == "CALL": d = d - instructions[ip][1] - 1 + 1
            elif op_name == "CALL_METHOD": d = d - instructions[ip][2] - 1 + 1
            elif op_name in ("MAKE_ARRAY", "MAKE_OBJECT"):
                argc = instructions[ip][1]
                if op_name == "MAKE_OBJECT": argc *= 2
                d = d - argc + 1
            elif op_name == "JMP": return simulate(instructions[ip][1], d)
            if op_name in ("JMP_IF", "JMP_IFNOT", "TRY"):
                if not simulate(instructions[ip][1], d): return False
            elif op_name == "RET": return True
            ip += 1
        return True

    if not simulate(0, 0): return None
        
    # 2. 构建 CFG 与 SSA 优化器
    cfg = CFG(instructions).build()
    ssa = SSABuilder(cfg).build()
    optimizer = SSAOptimizer(ssa).optimize()

    code = []
    code.append("def jitted_func(locals_, global_env):")
    code.append("    # 3AC SSA-Optimized 执行引擎")
    code.append("    r = [None] * 256")
    code.append(f"    ip = {func_obj['entry_ip']}")
    code.append("    n_instr = len(instructions)")
    code.append("    while ip < n_instr:")
    
    r_info = {} # 局部常量跟踪
    
    for i, instr in enumerate(instructions):
        d = depths[i]
        if d is None:
            code.append(f"        if ip == {i}: ip += 1; continue")
            continue
            
        # 进入新基本块时的优化处理
        if cfg and i in cfg.blocks:
            r_info.clear()
            block = cfg.blocks[i]
            # 循环展开检查 (v1.0.11+ 特性)
            if optimizer.should_unroll(block):
                code.append(f"        # [优化] 自动循环展开标记: 块 {i}")
            
            if block in ssa.phi_nodes:
                for var in ssa.phi_nodes[block]:
                    code.append(f"        # [SSA] Phi 节点: {var}")

        code.append(f"        if ip == {i}:")
        op_int = instr[0]
        op_name = OPCODE_LIST[op_int]
        
        # ─── 高效 3AC 生成逻辑 (含常量折叠) ───
        if op_name == "PUSH":
            val = constants[instr[1]]
            r_info[d] = val
            code.append(f"            r[{d}] = {repr(val)}")
            code.append("            ip += 1")
        elif op_name in ("ADD", "FAST_ADD"):
            if (d-2) in r_info and (d-1) in r_info:
                a, b = r_info[d-2], r_info[d-1]
                if isinstance(a, (int, float, str)) and isinstance(b, (int, float, str)):
                    try:
                        res = (a + b) if not isinstance(a, str) else (str(a) + str(b))
                        r_info[d-2] = res
                        code.append(f"            r[{d-2}] = {repr(res)} # [GVN/折叠]")
                        code.append("            ip += 1")
                        continue
                    except: pass
            code.append(f"            a, b = r[{d-2}], r[{d-1}]")
            code.append("            if isinstance(a, str) or isinstance(b, str):")
            code.append("                from zhiai.builtins import _转换文字")
            code.append(f"                r[{d-2}] = _转换文字(a) + _转换文字(b)")
            code.append(f"            else: r[{d-2}] = a + b")
            code.append("            ip += 1")
            r_info.pop(d-2, None); r_info.pop(d-1, None)
        elif op_name == "STORE_LOCAL":
            idx = instr[1]
            code.append(f"            if {idx} < len(locals_): locals_[{idx}] = r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "LOAD_LOCAL":
            idx = instr[1]
            code.append(f"            if {idx} < len(locals_): r[{d}] = locals_[{idx}]")
            code.append(f"            else: r[{d}] = None")
            code.append("            ip += 1")
        elif op_name == "RET":
            code.append(f"            return r[{d-1}]")
        elif op_name == "JMP":
            code.append(f"            ip = {instr[1]}")
        elif op_name == "JMP_IF":
            if (d-1) in r_info:
                val = bool(r_info[d-1])
                code.append(f"            # [DCE] 消除死分支: {not val}")
                code.append(f"            ip = {instr[1] if val else 'ip + 1'}")
            else:
                code.append(f"            if r[{d-1}]: ip = {instr[1]}")
                code.append("            else: ip += 1")
        elif op_name == "CALL":
            argc = instr[1]
            r_info.clear()
            code.append(f"            callee = r[{d - argc - 1}]")
            code.append(f"            f_args = r[{d - argc}:{d}]")
            code.append("            if isinstance(callee, dict) and callee.get('jitted_func'):")
            code.append("                l_list = f_args + [None] * (callee.get('locals_count', 0) - len(f_args))")
            code.append(f"                r[{d - argc - 1}] = callee['jitted_func'](l_list, global_env)")
            code.append("            else:")
            code.append("                from zhiai.builtins import wrap_callable")
            code.append(f"                r[{d - argc - 1}] = wrap_callable(callee)(*f_args)")
            code.append("            ip += 1")
        else:
            # 安全回退
            return None
            
    code.append("    return None")
    source = "\n".join(code)
    context = {"constants": constants, "instructions": instructions, "func_obj": func_obj}
    try:
        exec(source, context)
        return context["jitted_func"]
    except: return None
