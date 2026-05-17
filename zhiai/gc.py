# -*- coding: utf-8 -*-
"""致爱精确式垃圾回收器 (Exact Garbage Collector)"""

class MarkSweepGC:
    def __init__(self, vm):
        self.vm = vm
        self.tracked = set()
        self.threshold = 300  # 触发GC的分配对象阈值
        self.gc_runs = 0
        self.collected_count = 0
        
    def track(self, obj):
        """将动态分配的对象注册到GC监控队列"""
        if obj is not None and (isinstance(obj, (dict, list)) or hasattr(obj, 'fields')):
            self.tracked.add(id(obj))
            # 记录对象引用，防范Python提前销毁
            if not hasattr(self, '_keep_alive'):
                self._keep_alive = {}
            self._keep_alive[id(obj)] = obj
            
            if len(self.tracked) > self.threshold:
                self.collect()
                
    def collect(self):
        """执行一次精确式 Mark-and-Sweep 垃圾回收"""
        self.gc_runs += 1
        marked = set()
        
        # 1. 寻找 GC 根节点 (Roots)
        roots = []
        # 求值栈
        roots.extend(self.vm.stack)
        # 全局环境变量
        if self.vm.global_env:
            roots.extend(self.vm.global_env.vars.values())
        # 调用栈活跃帧的局部变量与闭包环境
        for frame in self.vm.call_stack:
            roots.extend(frame.locals)
            curr_env = frame.env
            while curr_env:
                roots.extend(curr_env.vars.values())
                curr_env = curr_env.parent
                
        # 2. 标记阶段 (Mark Phase)
        to_visit = [r for r in roots if self._is_trackable(r)]
        while to_visit:
            curr = to_visit.pop()
            curr_id = id(curr)
            if curr_id in marked:
                continue
            marked.add(curr_id)
            
            # 深度遍历子节点引用
            if hasattr(curr, 'fields'):  # Instance 实例
                for f in curr.fields:
                    if self._is_trackable(f):
                        to_visit.append(f)
            elif isinstance(curr, list):
                for item in curr:
                    if self._is_trackable(item):
                        to_visit.append(item)
            elif isinstance(curr, dict):
                for v in curr.values():
                    if self._is_trackable(v):
                        to_visit.append(v)
                        
        # 3. 清扫阶段 (Sweep Phase)
        unreachable_ids = self.tracked - marked
        swept = 0
        for uid in unreachable_ids:
            obj = self._keep_alive.get(uid)
            if obj is not None:
                swept += 1
                # 主动断开循环引用与内部关联，释放内存
                if hasattr(obj, 'fields'):
                    obj.fields = []
                elif isinstance(obj, list):
                    obj.clear()
                elif isinstance(obj, dict):
                    obj.clear()
                del self._keep_alive[uid]
                
        self.collected_count += swept
        self.tracked = marked
        return swept

    def _is_trackable(self, val):
        return val is not None and (isinstance(val, (dict, list)) or hasattr(val, 'fields'))
