# -*- coding: utf-8 -*-
"""致爱控制流图 (Control Flow Graph) 构建器"""

from zhiai.vm import OPCODE_LIST

class BasicBlock:
    """基本块：一段连续执行且没有跳转进出的代码指令序列"""
    def __init__(self, start_ip):
        self.start_ip = start_ip
        self.end_ip = -1
        self.instructions = []
        self.predecessors = [] # 前驱块
        self.successors = []   # 后继块
        self.is_entry = False
        self.is_exit = False

    def __repr__(self):
        return f"Block[{self.start_ip}:{self.end_ip}] (Succ: {[s.start_ip for s in self.successors]})"

class CFG:
    """控制流图：由基本块及其连接关系构成的有向图"""
    def __init__(self, instructions):
        self.instructions = instructions
        self.blocks = {} # start_ip -> BasicBlock
        self.entry_block = None

    def build(self):
        if not self.instructions:
            return
            
        # 1. 识别领导者 (Leaders) - 基本块的起点
        leaders = {0} # 入口指令是领导者
        for ip, instr in enumerate(self.instructions):
            op_name = OPCODE_LIST[instr[0]]
            
            if op_name in ("JMP", "JMP_IF", "JMP_IFNOT", "TRY", "RET", "RAISE", "HALT"):
                # 跳转指令的下一条指令是领导者
                if ip + 1 < len(self.instructions):
                    leaders.add(ip + 1)
                # 跳转的目标指令是领导者
                if op_name in ("JMP", "JMP_IF", "JMP_IFNOT", "TRY"):
                    target = instr[1]
                    leaders.add(target)
        
        sorted_leaders = sorted(list(leaders))
        
        # 2. 创建基本块
        for i, start_ip in enumerate(sorted_leaders):
            block = BasicBlock(start_ip)
            if i == 0:
                block.is_entry = True
                self.entry_block = block
            
            # 确定块的范围
            end_ip = sorted_leaders[i+1] if i + 1 < len(sorted_leaders) else len(self.instructions)
            block.end_ip = end_ip
            block.instructions = self.instructions[start_ip:end_ip]
            self.blocks[start_ip] = block

        # 3. 建立连接关系 (Successors/Predecessors)
        for start_ip, block in self.blocks.items():
            last_instr = block.instructions[-1]
            last_ip = block.end_ip - 1
            op_name = OPCODE_LIST[last_instr[0]]
            
            # 终止性指令
            if op_name == "JMP":
                self._add_edge(block, last_instr[1])
            elif op_name in ("JMP_IF", "JMP_IFNOT", "TRY"):
                # 分支：可能跳，也可能走下一行
                self._add_edge(block, last_instr[1])
                if last_ip + 1 < len(self.instructions):
                    self._add_edge(block, last_ip + 1)
            elif op_name in ("RET", "HALT", "RAISE"):
                block.is_exit = True
            else:
                # 顺序流向下一个块
                if last_ip + 1 < len(self.instructions):
                    self._add_edge(block, last_ip + 1)
        
        return self

    def _add_edge(self, from_block, to_ip):
        if to_ip in self.blocks:
            to_block = self.blocks[to_ip]
            if to_block not in from_block.successors:
                from_block.successors.append(to_block)
            if from_block not in to_block.predecessors:
                to_block.predecessors.append(from_block)

    def visualize(self):
        """生成 Mermaid 图表源码"""
        lines = ["graph TD"]
        for block in self.blocks.values():
            label = f"B{block.start_ip}[块 {block.start_ip}-{block.end_ip-1}]"
            lines.append(f"    {label}")
            for succ in block.successors:
                lines.append(f"    B{block.start_ip} --> B{succ.start_ip}")
        return "\n".join(lines)
