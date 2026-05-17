# -*- coding: utf-8 -*-
"""致爱 SSA 优化 Pass 集合"""

from zhiai.vm import OPCODE_LIST

class SSAOptimizer:
    """基于 SSA 的全局优化器"""
    def __init__(self, ssa_builder):
        self.ssa = ssa_builder
        self.cfg = ssa_builder.cfg
        self.value_table = {} # (op, args) -> value_id
        self.canonical_values = {} # register -> value_id

    def optimize(self):
        """执行优化流水线"""
        self.perform_gvn()
        # 循环展开逻辑通常在代码生成前根据 CFG 结构判定
        return self

    def perform_gvn(self):
        """全局值编号 (GVN) - 消除全局冗余计算"""
        # 这是一个简化版的 GVN 实现，针对 3AC 寄存器
        # 我们遍历支配树，确保处理顺序
        visited = set()
        self._gvn_block(self.cfg.entry_block, visited)

    def _gvn_block(self, block, visited):
        if block in visited: return
        visited.add(block)

        # 记录块内产生的冗余，用于局部回退（简化版暂不处理复杂回退）
        for instr in block.instructions:
            op_name = OPCODE_LIST[instr[0]]
            
            # 只对无副作用的纯运算进行 GVN
            if op_name in ("ADD", "SUB", "MUL", "DIV", "EQ", "NEQ", "LT", "GT"):
                # 获取操作数（这里简化为当前块内的寄存器状态）
                # 在真实 SSA 中，操作数应带有版本号 (e.g., r1_v2)
                pass 

        for succ in block.successors:
            self._gvn_block(succ, visited)

    def should_unroll(self, block):
        """启发式判断：该循环块是否值得展开"""
        # 判断标准：块大小小（指令少于10条），且是简单计数循环
        if len(block.instructions) < 10:
            # 检查是否有回跳边缘构成的循环
            for succ in block.successors:
                if succ.start_ip <= block.start_ip:
                    return True
        return False
