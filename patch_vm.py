import os

def patch():
    f = 'zhiai/vm.py'
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    # Add MATCH and TRY_PROPAGATE to OPCODE_LIST
    content = content.replace(
        '    "ASYNC_CALL", "AWAIT"\n]',
        '    "ASYNC_CALL", "AWAIT", "MATCH", "TRY_PROPAGATE"\n]'
    )

    # Register handlers
    content = content.replace(
        '            "ASYNC_CALL": self._op_ASYNC_CALL,\n            "AWAIT": self._op_AWAIT,\n        }',
        '            "ASYNC_CALL": self._op_ASYNC_CALL,\n            "AWAIT": self._op_AWAIT,\n            "MATCH": self._op_MATCH,\n            "TRY_PROPAGATE": self._op_TRY_PROPAGATE,\n        }'
    )

    # Implement _op_MATCH and _op_TRY_PROPAGATE
    impl = """
    def _op_MATCH(self, instr):
        # instr: [MATCH, branch_count, default_ip]
        branch_count = instr[1]
        default_ip = instr[2]
        target = self.pop()
        
        # 依次检查每个分支 (pattern, target_ip)
        for _ in range(branch_count):
            pattern = self.pop()
            target_ip = self.pop()
            if target == pattern:
                self.ip = target_ip
                return
                
        # 都不匹配，走默认
        self.ip = default_ip

    def _op_TRY_PROPAGATE(self, instr):
        val = self.pop()
        if hasattr(val, "是失败") and val.是失败():
             self._op_RET([OPCODE_MAP["RET"]])
             return
        if hasattr(val, "是空") and val.是空():
             self._op_RET([OPCODE_MAP["RET"]])
             return
        if hasattr(val, "获取"):
            self.push(val.获取())
        else:
            self.push(val)

    def _op_BREAKPOINT(self, instr):"""
    content = content.replace('    def _op_BREAKPOINT(self, instr):', impl)

    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

patch()
