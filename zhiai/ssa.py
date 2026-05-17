# -*- coding: utf-8 -*-
"""致爱 SSA (Static Single Assignment) 分析引擎"""

from zhiai.cfg import CFG, BasicBlock

def compute_dominators(cfg):
    """计算支配树 (Dominator Tree)"""
    if not cfg.entry_block:
        return {}
    
    blocks = list(cfg.blocks.values())
    dom = {block: set(blocks) for block in blocks}
    dom[cfg.entry_block] = {cfg.entry_block}
    
    changed = True
    while changed:
        changed = False
        for block in blocks:
            if block == cfg.entry_block:
                continue
            if not block.predecessors:
                continue
            
            # 交集所有前驱的支配集
            new_dom = set.intersection(*(dom[p] for p in block.predecessors))
            new_dom.add(block)
            
            if new_dom != dom[block]:
                dom[block] = new_dom
                changed = True
    return dom

def compute_strict_dominators(dom):
    """计算严格支配集"""
    sdom = {}
    for block, doms in dom.items():
        sdom[block] = doms - {block}
    return sdom

def compute_immediate_dominators(sdom):
    """计算直接支配节点 (Immediate Dominator)"""
    idom = {}
    for block, sdoms in sdom.items():
        if not sdoms:
            idom[block] = None
            continue
        for d in sdoms:
            is_idom = True
            for x in sdoms:
                if x != d and d in sdom.get(x, set()):
                    is_idom = False
                    break
            if is_idom:
                idom[block] = d
                break
    return idom

def compute_dominance_frontier(cfg, idom):
    """计算支配边界 (Dominance Frontier)"""
    df = {block: set() for block in cfg.blocks.values()}
    for block in cfg.blocks.values():
        if len(block.predecessors) >= 2:
            for p in block.predecessors:
                runner = p
                while runner and runner != idom.get(block):
                    df[runner].add(block)
                    runner = idom.get(runner)
    return df

class SSABuilder:
    def __init__(self, cfg):
        self.cfg = cfg
        self.dom = {}
        self.idom = {}
        self.df = {}
        self.phi_nodes = {} # block -> set(var_names)

    def build(self):
        self.dom = compute_dominators(self.cfg)
        sdom = compute_strict_dominators(self.dom)
        self.idom = compute_immediate_dominators(sdom)
        self.df = compute_dominance_frontier(self.cfg, self.idom)
        return self

    def insert_phi_for_var(self, var_name, def_blocks):
        """为特定变量插入 Phi 函数
        def_blocks: 定义该变量的 block 集合
        """
        worklist = list(def_blocks)
        inserted = set()
        
        while worklist:
            b = worklist.pop(0)
            for d in self.df.get(b, []):
                if d not in inserted:
                    inserted.add(d)
                    if d not in self.phi_nodes:
                        self.phi_nodes[d] = set()
                    self.phi_nodes[d].add(var_name)
                    if d not in def_blocks:
                        worklist.append(d)
