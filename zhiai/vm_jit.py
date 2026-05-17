# -*- coding: utf-8 -*-
"""致爱方法级 JIT 编译器 (Method JIT Compiler - 3AC/SSA Optimized)"""

import sys
from zhiai.vm import OPCODE_LIST
from zhiai.cfg import CFG
from zhiai.ssa import SSABuilder

def compile_function(func_obj, global_env):
    """动态将致爱字节码函数 JIT 编译为高效的三地址码 (3AC) 形式的原生 Python 代码 (支持高级优化)"""
    instructions = func_obj["instructions"]
    constants = func_obj["constants"]
    
    cfg = CFG(instructions)
    cfg.build()
    
    depths = [None] * len(instructions)
    def analyze_block(block, start_depth):
        d = start_depth
        for ip_offset, instr in enumerate(block.instructions):
            ip = block.start_ip + ip_offset
            if depths[ip] is not None:
                if depths[ip] != d: return False
                return True
            depths[ip] = d
            op_int = instr[0]
            op_name = OPCODE_LIST[op_int]
            if op_name in ("PUSH", "LOAD_LOCAL", "LOAD", "LOAD_GLOBAL", "LOAD_INDEX", "LOAD_PROP", "NEW"): d += 1
            elif op_name in ("POP", "STORE_LOCAL", "STORE", "STORE_GLOBAL", "PRINT", "RAISE", "JMP_IF", "JMP_IFNOT", "NOT"): d -= 1
            elif op_name in ("ADD", "FAST_ADD", "SUB", "FAST_SUB", "MUL", "DIV", "MOD", "POW", "EQ", "NEQ", "LT", "GT", "LTE", "GTE", "AND", "OR", "BINOP"): d -= 1 
            elif op_name in ("STORE_INDEX", "STORE_PROP"): d -= 2 
            elif op_name == "CALL": d = d - instr[1] - 1 + 1
            elif op_name == "CALL_METHOD": d = d - instr[2] - 1 + 1
            elif op_name in ("MAKE_ARRAY", "MAKE_OBJECT"):
                argc = instr[1]
                if op_name == "MAKE_OBJECT": argc *= 2
                d = d - argc + 1
        for succ in block.successors:
            if not analyze_block(succ, d): return False
        return True

    if not analyze_block(cfg.entry_block, 0):
        return None 

    ssa_builder = SSABuilder(cfg)
    ssa_builder.build()
    local_defs = {}
    if cfg.blocks:
        for block in cfg.blocks.values():
            for instr in block.instructions:
                if OPCODE_LIST[instr[0]] == "STORE_LOCAL":
                    var_name = f"local_{instr[1]}"
                    if var_name not in local_defs: local_defs[var_name] = set()
                    local_defs[var_name].add(block)
        for var_name, def_blocks in local_defs.items():
            ssa_builder.insert_phi_for_var(var_name, def_blocks)

    code = []
    code.append("def jitted_func(locals_, global_env):")
    code.append("    # 3-Address Code 虚拟寄存器组 & 预分配 SSA 节点")
    code.append("    r = [None] * 256")
    code.append(f"    ip = {func_obj['entry_ip']}")
    code.append("    n_instr = len(instructions)")
    code.append("    while ip < n_instr:")
    
    r_info = {} # 寄存器常量跟踪 (用于常量折叠和强度削弱)

    for i, instr in enumerate(instructions):
        d = depths[i]
        
        if cfg.blocks and i in cfg.blocks:
            r_info.clear() # 进入新基本块，重置状态
            block = cfg.blocks[i]
            if block in ssa_builder.phi_nodes:
                for var_name in ssa_builder.phi_nodes[block]:
                    pred_labels = [f"B{p.start_ip}" for p in block.predecessors]
                    code.append(f"        # Phi Node: {var_name} = Φ({', '.join(pred_labels)})")

        if d is None:
            code.append(f"        if ip == {i}:")
            code.append("            ip += 1; continue")
            continue
            
        code.append(f"        if ip == {i}:")
        op_int = instr[0]
        op_name = OPCODE_LIST[op_int] if op_int < len(OPCODE_LIST) else str(op_int)
        
        if op_name == "PUSH":
            val = constants[instr[1]]
            r_info[d] = val
            code.append(f"            r[{d}] = {repr(val)}")
            code.append("            ip += 1")
        elif op_name == "POP":
            r_info.pop(d-1, None)
            code.append("            ip += 1")
        elif op_name == "DUP":
            if (d-1) in r_info: r_info[d] = r_info[d-1]
            code.append(f"            r[{d}] = r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "LOAD_LOCAL":
            r_info.pop(d, None)
            idx = instr[1]
            code.append(f"            if {idx} < len(locals_): r[{d}] = locals_[{idx}]")
            code.append(f"            else: r[{d}] = None")
            code.append("            ip += 1")
        elif op_name == "STORE_LOCAL":
            r_info.pop(d-1, None)
            idx = instr[1]
            code.append(f"            if {idx} < len(locals_): locals_[{idx}] = r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "LOAD":
            r_info.pop(d, None)
            code.append(f"            r[{d}] = global_env.get(constants[{instr[1]}])")
            code.append("            ip += 1")
        elif op_name == "STORE":
            r_info.pop(d-1, None)
            code.append(f"            global_env.define(constants[{instr[1]}], r[{d-1}])")
            code.append("            ip += 1")
        elif op_name in ("ADD", "FAST_ADD"):
            # 常量折叠
            if (d-2) in r_info and (d-1) in r_info:
                a, b = r_info[d-2], r_info[d-1]
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    res = a + b
                    r_info[d-2] = res
                    code.append(f"            r[{d-2}] = {repr(res)} # 常量折叠")
                    code.append("            ip += 1")
                    r_info.pop(d-1, None)
                    continue
                elif isinstance(a, str) or isinstance(b, str):
                    res = str(a) + str(b)
                    r_info[d-2] = res
                    code.append(f"            r[{d-2}] = {repr(res)} # 常量折叠")
                    code.append("            ip += 1")
                    r_info.pop(d-1, None)
                    continue
            # 强度削弱 (x + 0 -> x, 0 + x -> x)
            if (d-1) in r_info and r_info[d-1] == 0:
                code.append(f"            # 强度削弱: a + 0 -> a")
                code.append("            ip += 1")
                r_info.pop(d-1, None)
                continue
            if (d-2) in r_info and r_info[d-2] == 0:
                code.append(f"            r[{d-2}] = r[{d-1}] # 强度削弱: 0 + b -> b")
                code.append("            ip += 1")
                if (d-1) in r_info: r_info[d-2] = r_info[d-1]
                else: r_info.pop(d-2, None)
                r_info.pop(d-1, None)
                continue
                
            code.append(f"            a, b = r[{d-2}], r[{d-1}]")
            code.append("            if isinstance(a, str) or isinstance(b, str):")
            code.append("                from zhiai.builtins import _转换文字")
            code.append(f"                r[{d-2}] = _转换文字(a) + _转换文字(b)")
            code.append(f"            else: r[{d-2}] = a + b")
            code.append("            ip += 1")
            r_info.pop(d-2, None); r_info.pop(d-1, None)
        elif op_name in ("SUB", "FAST_SUB"):
            if (d-2) in r_info and (d-1) in r_info:
                a, b = r_info[d-2], r_info[d-1]
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    res = a - b
                    r_info[d-2] = res
                    code.append(f"            r[{d-2}] = {repr(res)} # 常量折叠")
                    code.append("            ip += 1")
                    r_info.pop(d-1, None)
                    continue
            if (d-1) in r_info and r_info[d-1] == 0:
                code.append(f"            # 强度削弱: a - 0 -> a")
                code.append("            ip += 1")
                r_info.pop(d-1, None)
                continue
            code.append(f"            r[{d-2}] = r[{d-2}] - r[{d-1}]")
            code.append("            ip += 1")
            r_info.pop(d-2, None); r_info.pop(d-1, None)
        elif op_name == "MUL":
            if (d-2) in r_info and (d-1) in r_info:
                a, b = r_info[d-2], r_info[d-1]
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    res = a * b
                    r_info[d-2] = res
                    code.append(f"            r[{d-2}] = {repr(res)} # 常量折叠")
                    code.append("            ip += 1")
                    r_info.pop(d-1, None)
                    continue
            # 强度削弱
            if ((d-1) in r_info and r_info[d-1] == 1):
                code.append(f"            # 强度削弱: a * 1 -> a")
                code.append("            ip += 1")
                r_info.pop(d-1, None)
                continue
            if ((d-2) in r_info and r_info[d-2] == 1):
                code.append(f"            r[{d-2}] = r[{d-1}] # 强度削弱: 1 * b -> b")
                code.append("            ip += 1")
                if (d-1) in r_info: r_info[d-2] = r_info[d-1]
                else: r_info.pop(d-2, None)
                r_info.pop(d-1, None)
                continue
            if ((d-1) in r_info and r_info[d-1] == 0) or ((d-2) in r_info and r_info[d-2] == 0):
                code.append(f"            r[{d-2}] = 0 # 强度削弱: x * 0 -> 0")
                code.append("            ip += 1")
                r_info[d-2] = 0
                r_info.pop(d-1, None)
                continue
            code.append(f"            r[{d-2}] = r[{d-2}] * r[{d-1}]")
            code.append("            ip += 1")
            r_info.pop(d-2, None); r_info.pop(d-1, None)
        elif op_name == "DIV":
            if (d-2) in r_info and (d-1) in r_info:
                a, b = r_info[d-2], r_info[d-1]
                if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b != 0:
                    res = a // b if isinstance(a, int) and isinstance(b, int) and a % b == 0 else a / b
                    r_info[d-2] = res
                    code.append(f"            r[{d-2}] = {repr(res)} # 常量折叠")
                    code.append("            ip += 1")
                    r_info.pop(d-1, None)
                    continue
            if (d-1) in r_info and r_info[d-1] == 1:
                code.append(f"            # 强度削弱: a / 1 -> a")
                code.append("            ip += 1")
                r_info.pop(d-1, None)
                continue
            code.append(f"            a, b = r[{d-2}], r[{d-1}]")
            code.append("            if b == 0: return None")
            code.append("            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b != 0:")
            code.append("                if isinstance(a, int) and isinstance(b, int) and a % b == 0:")
            code.append(f"                    r[{d-2}] = a // b")
            code.append("                else:")
            code.append(f"                    r[{d-2}] = a / b")
            code.append("            else: return None")
            code.append("            ip += 1")
            r_info.pop(d-2, None); r_info.pop(d-1, None)
        elif op_name in ("EQ", "NEQ", "LT", "GT", "LTE", "GTE", "AND", "OR"):
            r_info.pop(d-2, None); r_info.pop(d-1, None)
            if op_name == "EQ": code.append(f"            r[{d-2}] = r[{d-2}] == r[{d-1}]")
            elif op_name == "NEQ": code.append(f"            r[{d-2}] = r[{d-2}] != r[{d-1}]")
            elif op_name == "LT": code.append(f"            r[{d-2}] = r[{d-2}] < r[{d-1}]")
            elif op_name == "GT": code.append(f"            r[{d-2}] = r[{d-2}] > r[{d-1}]")
            elif op_name == "LTE": code.append(f"            r[{d-2}] = r[{d-2}] <= r[{d-1}]")
            elif op_name == "GTE": code.append(f"            r[{d-2}] = r[{d-2}] >= r[{d-1}]")
            elif op_name == "AND": code.append(f"            r[{d-2}] = r[{d-2}] and r[{d-1}]")
            elif op_name == "OR": code.append(f"            r[{d-2}] = r[{d-2}] or r[{d-1}]")
            code.append("            ip += 1")
        elif op_name == "RET":
            code.append(f"            return r[{d-1}]")
        elif op_name == "JMP":
            code.append(f"            ip = {instr[1]}")
        elif op_name == "JMP_IF":
            if (d-1) in r_info:
                val = bool(r_info[d-1])
                code.append(f"            # 死分支消除 (Constant Condition: {val})")
                if val: code.append(f"            ip = {instr[1]}")
                else: code.append("            ip += 1")
            else:
                code.append(f"            if r[{d-1}]:")
                code.append(f"                ip = {instr[1]}")
                code.append("            else:")
                code.append("                ip += 1")
            r_info.pop(d-1, None)
        elif op_name == "JMP_IFNOT":
            if (d-1) in r_info:
                val = bool(r_info[d-1])
                code.append(f"            # 死分支消除 (Constant Condition: {not val})")
                if not val: code.append(f"            ip = {instr[1]}")
                else: code.append("            ip += 1")
            else:
                code.append(f"            if not r[{d-1}]:")
                code.append(f"                ip = {instr[1]}")
                code.append("            else:")
                code.append("                ip += 1")
            r_info.pop(d-1, None)
        elif op_name == "CALL":
            argc = instr[1]
            r_info.clear() # 安全起见清空跟踪
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
        elif op_name == "CALL_METHOD":
            r_info.clear()
            argc = instr[2]
            code.append(f"            callee = r[{d - argc - 1}]")
            code.append(f"            func_args = r[{d - argc}:{d}]")
            code.append(f"            name = constants[{instr[1]}]")
            code.append("            if hasattr(callee, 'get_prop'):")
            code.append(f"                r[{d - argc - 1}] = callee.get_prop(name)(*func_args)")
            code.append("            elif isinstance(callee, dict):")
            code.append(f"                r[{d - argc - 1}] = callee.get(name)(*func_args)")
            code.append("            else:")
            code.append(f"                r[{d - argc - 1}] = getattr(callee, name)(*func_args)")
            code.append("            ip += 1")
        elif op_name == "LOAD_PROP":
            r_info.pop(d-1, None)
            code.append(f"            obj = r[{d-1}]")
            code.append(f"            name = constants[{instr[1]}]")
            code.append("            if hasattr(obj, 'get_prop'):")
            code.append(f"                r[{d-1}] = obj.get_prop(name)")
            code.append("            elif isinstance(obj, dict):")
            code.append(f"                r[{d-1}] = obj.get(name)")
            code.append("            else:")
            code.append(f"                r[{d-1}] = getattr(obj, name, None)")
            code.append("            ip += 1")
        else:
            # 遇到未完全适配 3AC 的指令，强制回退，保证正确性
            return None
            
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
