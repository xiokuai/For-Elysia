import os

def patch_vm_jit():
    f = 'zhiai/vm_jit.py'
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    # 1. Stack simulation: TRY_PROPAGATE pops 1, pushes 1. Net change 0.
    # It might branch out (return), but the continue path has same stack depth.
    # No need to add to stack depth change since net is 0, UNLESS it's explicitly matched.
    # Actually, if it's not matched, it might default to doing nothing (net 0) or error.
    # But wait, there is no "if op_name in ...: d += 0". It's fine.

    # 2. Add JIT compilation logic for TRY_PROPAGATE
    jit_logic = """
        elif op_name == "RET":
            code.append(f"            return r[{d-1}]")
        elif op_name == "TRY_PROPAGATE":
            code.append(f"            val = r[{d-1}]")
            code.append("            if hasattr(val, '是失败') and val.是失败(): return val")
            code.append("            if hasattr(val, '是空') and val.是空(): return val")
            code.append(f"            if hasattr(val, '获取'): r[{d-1}] = val.获取()")
            code.append("            ip += 1")
"""
    content = content.replace(
        '        elif op_name == "RET":\n            code.append(f"            return r[{d-1}]")\n',
        jit_logic
    )

    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

patch_vm_jit()
