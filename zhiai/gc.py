# -*- coding: utf-8 -*-
"""致爱精确式增量垃圾回收器 (Incremental Exact Garbage Collector)"""

class IncrementalGC:
    """增量式三色标记垃圾回收器"""
    def __init__(self, vm):
        self.vm = vm
        self.tracked = set()       # 所有被追踪的对象 ID (白色集)
        self.marked = set()        # 黑色集 (已扫描完成)
        self.gray = []             # 灰色集 (待扫描子节点)
        self.threshold = 500       # 触发 GC 的分配对象阈值
        self.gc_runs = 0
        self.collected_count = 0
        self.state = "IDLE"        # 状态: IDLE, MARKING, SWEEPING
        self._keep_alive = {}
        self.steps_per_alloc = 5   # 每次分配时执行的扫描步数
        
    def track(self, obj):
        """将动态分配的对象注册到GC监控队列"""
        if self._is_trackable(obj):
            uid = id(obj)
            self.tracked.add(uid)
            self._keep_alive[uid] = obj
            
            # 如果正在标记阶段分配新对象，直接将其标为黑色或灰色，防止误回收
            if self.state == "MARKING":
                self.marked.add(uid)
                self.gray.append(obj)
            
            if self.state == "IDLE" and len(self.tracked) > self.threshold:
                self.start_gc()
            
            if self.state != "IDLE":
                self.step()

    def write_barrier(self, obj):
        """写屏障 (Write Barrier)
        当对象的引用关系发生改变时（如 obj.prop = val, arr[i] = val），
        如果是在 MARKING 阶段，我们需要将被写入的新值标为灰色（Dijkstra 风格），
        防止黑色对象引用了白色对象导致白色对象被错误回收。
        """
        if self.state == "MARKING" and self._is_trackable(obj):
            uid = id(obj)
            if uid not in self.marked:
                self.marked.add(uid)
                self.gray.append(obj)

    def start_gc(self):
        """启动新一轮增量 GC"""
        self.state = "MARKING"
        self.marked.clear()
        self.gray.clear()
        
        # 寻找 GC 根节点
        roots = []
        roots.extend(self.vm.stack)
        if self.vm.global_env:
            roots.extend(self.vm.global_env.vars.values())
        for frame in self.vm.call_stack:
            roots.extend(frame.locals)
            curr_env = frame.env
            while curr_env:
                roots.extend(curr_env.vars.values())
                curr_env = curr_env.parent
                
        # 初始化灰色集
        for r in roots:
            if self._is_trackable(r):
                uid = id(r)
                if uid not in self.marked:
                    self.marked.add(uid)
                    self.gray.append(r)

    def step(self):
        """执行一小步 GC 工作"""
        if self.state == "MARKING":
            steps = self.steps_per_alloc
            while self.gray and steps > 0:
                curr = self.gray.pop()
                steps -= 1
                
                # 扫描子节点
                if hasattr(curr, 'fields'):
                    for f in curr.fields:
                        if self._is_trackable(f) and id(f) not in self.marked:
                            self.marked.add(id(f))
                            self.gray.append(f)
                elif isinstance(curr, list):
                    for item in curr:
                        if self._is_trackable(item) and id(item) not in self.marked:
                            self.marked.add(id(item))
                            self.gray.append(item)
                elif isinstance(curr, dict):
                    for v in curr.values():
                        if self._is_trackable(v) and id(v) not in self.marked:
                            self.marked.add(id(v))
                            self.gray.append(v)
                            
            if not self.gray:
                self.state = "SWEEPING"
                self._sweep_iterator = iter(list(self.tracked - self.marked))
                
        elif self.state == "SWEEPING":
            steps = self.steps_per_alloc * 2
            try:
                for _ in range(steps):
                    uid = next(self._sweep_iterator)
                    obj = self._keep_alive.get(uid)
                    if obj is not None:
                        self.collected_count += 1
                        if hasattr(obj, 'fields'): obj.fields = []
                        elif isinstance(obj, list): obj.clear()
                        elif isinstance(obj, dict): obj.clear()
                        del self._keep_alive[uid]
                    self.tracked.remove(uid)
            except StopIteration:
                self.state = "IDLE"
                self.gc_runs += 1
                # 重新计算阈值
                self.threshold = max(500, len(self.tracked) * 2)

    def collect(self):
        """强制执行完整的全堆回收 (STW)"""
        if self.state == "IDLE":
            self.start_gc()
        while self.state != "IDLE":
            self.step()

    def _is_trackable(self, val):
        return val is not None and (isinstance(val, (dict, list)) or hasattr(val, 'fields'))
