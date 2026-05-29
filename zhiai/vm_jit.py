"""将致爱寄存器字节码 JIT 编译为高效的原生 Python 代码 (v1.1.0 架构)"""

from zhiai.register_vm import OPCODE_LIST

def jit_compile(func_obj):
    instructions = func_obj["instructions"]
    constants = func_obj["constants"]

    code = []
    code.append("def jitted_func(locals_, global_env):")
    code.append("    # Register-based 3AC JIT 执行引擎")
    code.append("    r = [None] * 256")
    code.append("    for i, val in enumerate(locals_):")
    code.append("        r[i] = val")
    code.append(f"    ip = {func_obj.get('entry_ip', 0)}")
    code.append("    ")
    code.append("    while True:")
    code.append("        if ip == -1: break")

    for i, instr in enumerate(instructions):
        op_name = OPCODE_LIST[instr[0]]
        code.append(f"        if ip == {i}:")
        
        if op_name == "LOAD_CONST":
            code.append(f"            r[{instr[1]}] = constants[{instr[2]}]")
            code.append("            ip += 1")
        elif op_name == "LOAD_GLOBAL":
            code.append(f"            r[{instr[1]}] = global_env.get(constants[{instr[2]}])")
            code.append("            ip += 1")
        elif op_name == "STORE_GLOBAL":
            code.append(f"            global_env.set(constants[{instr[1]}], r[{instr[2]}])")
            code.append("            ip += 1")
        elif op_name == "DEF_GLOBAL":
            code.append(f"            global_env.define(constants[{instr[1]}], r[{instr[2]}])")
            code.append("            ip += 1")
        elif op_name == "MOVE":
            code.append(f"            r[{instr[1]}] = r[{instr[2]}]")
            code.append("            ip += 1")
        elif op_name == "LOAD_NULL":
            code.append(f"            r[{instr[1]}] = None")
            code.append("            ip += 1")
        elif op_name == "LOAD_BOOL":
            code.append(f"            r[{instr[1]}] = {repr(bool(instr[2]))}")
            code.append("            ip += 1")
        elif op_name == "ADD":
            code.append(f"            a = r[{instr[2]}]; b = r[{instr[3]}]")
            code.append(f"            r[{instr[1]}] = str(a) + str(b) if isinstance(a, str) or isinstance(b, str) else a + b")
            code.append("            ip += 1")
        elif op_name == "SUB":
            code.append(f"            r[{instr[1]}] = r[{instr[2]}] - r[{instr[3]}]")
            code.append("            ip += 1")
        elif op_name == "MUL":
            code.append(f"            r[{instr[1]}] = r[{instr[2]}] * r[{instr[3]}]")
            code.append("            ip += 1")
        elif op_name == "DIV":
            code.append(f"            a = r[{instr[2]}]; b = r[{instr[3]}]")
            code.append(f"            r[{instr[1]}] = a // b if isinstance(a, int) and isinstance(b, int) and a % b == 0 else a / b")
            code.append("            ip += 1")
        elif op_name == "MOD":
            code.append(f"            r[{instr[1]}] = r[{instr[2]}] % r[{instr[3]}]")
            code.append("            ip += 1")
        elif op_name == "POW":
            code.append(f"            r[{instr[1]}] = r[{instr[2]}] ** r[{instr[3]}]")
            code.append("            ip += 1")
        elif op_name == "EQ":
            code.append(f"            r[{instr[1]}] = r[{instr[2]}] == r[{instr[3]}]")
            code.append("            ip += 1")
        elif op_name == "NEQ":
            code.append(f"            r[{instr[1]}] = r[{instr[2]}] != r[{instr[3]}]")
            code.append("            ip += 1")
        elif op_name == "LT":
            code.append(f"            r[{instr[1]}] = r[{instr[2]}] < r[{instr[3]}]")
            code.append("            ip += 1")
        elif op_name == "GT":
            code.append(f"            r[{instr[1]}] = r[{instr[2]}] > r[{instr[3]}]")
            code.append("            ip += 1")
        elif op_name == "LTE":
            code.append(f"            r[{instr[1]}] = r[{instr[2]}] <= r[{instr[3]}]")
            code.append("            ip += 1")
        elif op_name == "GTE":
            code.append(f"            r[{instr[1]}] = r[{instr[2]}] >= r[{instr[3]}]")
            code.append("            ip += 1")
        elif op_name == "NEG":
            code.append(f"            r[{instr[1]}] = -r[{instr[2]}]")
            code.append("            ip += 1")
        elif op_name == "NOT":
            code.append(f"            val = r[{instr[2]}]")
            code.append("            truthy = False if val is None or val is False or val == 0 or val == '' or val == [] or val == {} else True")
            code.append(f"            r[{instr[1]}] = not truthy")
            code.append("            ip += 1")
        elif op_name == "LOAD_INDEX":
            code.append(f"            obj = r[{instr[2]}]")
            code.append(f"            idx_val = r[{instr[3]}]")
            code.append("            if isinstance(obj, (list, str)):")
            code.append("                idx = int(idx_val)")
            code.append("                if idx < 0: idx += len(obj)")
            code.append(f"                r[{instr[1]}] = obj[idx]")
            code.append("            elif isinstance(obj, dict):")
            code.append(f"                r[{instr[1]}] = obj.get(idx_val)")
            code.append("            ip += 1")
        elif op_name == "STORE_INDEX":
            code.append(f"            obj = r[{instr[1]}]")
            code.append(f"            idx_val = r[{instr[2]}]")
            code.append(f"            val = r[{instr[3]}]")
            code.append("            if isinstance(obj, list):")
            code.append("                idx = int(idx_val)")
            code.append("                if idx < 0: idx += len(obj)")
            code.append("                obj[idx] = val")
            code.append("            elif isinstance(obj, dict): obj[idx_val] = val")
            code.append("            ip += 1")
        elif op_name == "LOAD_PROP":
            code.append(f"            obj = r[{instr[2]}]")
            code.append(f"            name = constants[{instr[3]}]")
            code.append("            if hasattr(obj, 'get_prop'):")
            code.append(f"                r[{instr[1]}] = obj.get_prop(name)")
            code.append("            elif isinstance(obj, dict):")
            code.append(f"                r[{instr[1]}] = obj.get(name)")
            code.append("            elif isinstance(obj, str):")
            code.append("                if name == '长度':")
            code.append(f"                    r[{instr[1]}] = len(obj)")
            code.append("                else:")
            code.append("                    from zhiai.builtins import STRING_METHODS")
            code.append(f"                    r[{instr[1]}] = lambda *a: STRING_METHODS[name](obj, *a)")
            code.append("            elif isinstance(obj, list):")
            code.append("                if name == '长度':")
            code.append(f"                    r[{instr[1]}] = len(obj)")
            code.append("                else:")
            code.append("                    from zhiai.builtins import ARRAY_METHODS")
            code.append(f"                    r[{instr[1]}] = lambda *a: ARRAY_METHODS[name](obj, *a)")
            code.append("            else:")
            code.append(f"                r[{instr[1]}] = getattr(obj, name, None)")
            code.append("            ip += 1")
        elif op_name == "STORE_PROP":
            code.append(f"            obj = r[{instr[1]}]")
            code.append(f"            name = constants[{instr[2]}]")
            code.append(f"            val = r[{instr[3]}]")
            code.append("            if hasattr(obj, 'set_prop'): obj.set_prop(name, val)")
            code.append("            elif isinstance(obj, dict): obj[name] = val")
            code.append("            else: setattr(obj, name, val)")
            code.append("            ip += 1")
        elif op_name == "JMP":
            code.append(f"            ip = {instr[1]}")
        elif op_name == "JMP_IF":
            code.append(f"            val = r[{instr[1]}]")
            code.append("            truthy = False if val is None or val is False or val == 0 or val == '' or val == [] or val == {} else True")
            code.append(f"            ip = {instr[2]} if truthy else ip + 1")
        elif op_name == "JMP_IFNOT":
            code.append(f"            val = r[{instr[1]}]")
            code.append("            truthy = False if val is None or val is False or val == 0 or val == '' or val == [] or val == {} else True")
            code.append(f"            ip = {instr[2]} if not truthy else ip + 1")
        elif op_name == "CALL":
            arg_list = [f"r[{instr[3] + j}]" for j in range(instr[4])]
            code.append(f"            callee = r[{instr[2]}]")
            code.append(f"            if callable(callee):")
            code.append(f"                from zhiai.builtins import wrap_callable")
            code.append(f"                r[{instr[1]}] = wrap_callable(callee)({', '.join(arg_list)})")
            code.append(f"            else:")
            code.append(f"                r[{instr[1]}] = None # Handle function objects if needed")
            code.append("            ip += 1")
        elif op_name == "CALL_METHOD":
            arg_list = [f"r[{instr[4] + j}]" for j in range(instr[5])]
            code.append(f"            obj = r[{instr[2]}]")
            code.append(f"            method_name = constants[{instr[3]}]")
            code.append("            if hasattr(obj, 'klass'):")
            code.append("                method = obj.klass['methods'].get(method_name)")
            code.append("                # Simplification: call Python native method if possible")
            code.append(f"                r[{instr[1]}] = None")
            code.append("            elif isinstance(obj, list):")
            code.append("                from zhiai.builtins import ARRAY_METHODS")
            code.append(f"                r[{instr[1]}] = ARRAY_METHODS[method_name](obj, {', '.join(arg_list)})")
            code.append("            elif isinstance(obj, str):")
            code.append("                from zhiai.builtins import STRING_METHODS")
            code.append(f"                r[{instr[1]}] = STRING_METHODS[method_name](obj, {', '.join(arg_list)})")
            code.append("            else:")
            code.append("                method = getattr(obj, method_name, None)")
            code.append(f"                if callable(method): r[{instr[1]}] = method({', '.join(arg_list)})")
            code.append("            ip += 1")
        elif op_name == "RET":
            code.append(f"            return r[{instr[1]}]")
        elif op_name == "MAKE_ARRAY":
            arg_list = [f"r[{instr[2] + j}]" for j in range(instr[3])]
            code.append(f"            r[{instr[1]}] = [{', '.join(arg_list)}]")
            code.append("            ip += 1")
        elif op_name == "MAKE_OBJECT":
            pairs = []
            for j in range(instr[3]):
                pairs.append(f"r[{instr[2] + j*2}]: r[{instr[2] + j*2 + 1}]")
            code.append(f"            r[{instr[1]}] = {{{', '.join(pairs)}}}")
            code.append("            ip += 1")
        elif op_name == "MAKE_FUNC":
            # Simplified func creation for JIT
            code.append(f"            r[{instr[1]}] = {{'type': 'function', 'name': constants[{instr[2]}], 'arity': {instr[3]}, 'params': [constants[{instr[5]} + i] for i in range({instr[4]})], 'entry_ip': {instr[6]}, 'instructions': func_obj['instructions'], 'constants': constants, 'closure': global_env}}")
            code.append("            ip += 1")
        elif op_name == "TRY_PROPAGATE":
            code.append(f"            val = r[{instr[2]}]")
            code.append("            if hasattr(val, '是失败') and val.是失败(): return val")
            code.append("            if hasattr(val, '是空') and val.是空(): return val")
            code.append(f"            if hasattr(val, '获取'): r[{instr[1]}] = val.获取()")
            code.append(f"            else: r[{instr[1]}] = val")
            code.append("            ip += 1")
        elif op_name == "PRINT":
            code.append(f"            val = r[{instr[1]}]")
            code.append("            val_str = '空' if val is None else ('真' if val is True else ('假' if val is False else str(val)))")
            code.append("            print(val_str)")
            code.append("            ip += 1")
        elif op_name == "HALT":
            code.append("            return None")
        else:
            code.append(f"            # UNIMPLEMENTED: {op_name}")
            code.append("            ip += 1")

    code.append("    return None")
    source = "\n".join(code)
    
    # print(source) # For debugging if needed
    context = {"constants": constants, "instructions": instructions, "func_obj": func_obj}
    try:
        exec(source, context)
        return context["jitted_func"]
    except Exception as e:
        print(f"JIT Compilation Failed: {e}")
        return None
