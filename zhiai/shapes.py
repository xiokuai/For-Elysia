class Shape:
    """隐藏类 (Hidden Class / Shape)
    
    维护属性名到存储偏移量的映射。
    """
    # 类级别的转换路径全局缓存 (Transition Caching)
    _transition_cache = {}

    def __init__(self, parent=None, prop_name=None, offset=None):
        self.parent = parent
        self.prop_name = prop_name
        self.offset = offset
        self.transitions = {}  # 局部转换缓存: prop_name -> next_shape
        self.depth = (parent.depth + 1) if parent else 0
        self._offsets_cache = {}  # 属性偏移量缓存

    def get_offset(self, prop_name):
        """获取属性偏移量，使用带缓存的链式查找，避免字典复制"""
        if prop_name in self._offsets_cache:
            return self._offsets_cache[prop_name]
        
        curr = self
        while curr is not None:
            if curr.prop_name == prop_name:
                self._offsets_cache[prop_name] = curr.offset
                return curr.offset
            curr = curr.parent
            
        self._offsets_cache[prop_name] = None
        return None

    def transition(self, prop_name):
        """添加新属性并切换到下一个 Shape，使用全局和局部转换路径缓存"""
        # 1. 尝试从局部转换缓存获取
        if prop_name in self.transitions:
            return self.transitions[prop_name]
        
        # 2. 尝试从全局转换缓存获取
        cache_key = (self, prop_name)
        if cache_key in Shape._transition_cache:
            next_shape = Shape._transition_cache[cache_key]
            self.transitions[prop_name] = next_shape
            return next_shape
        
        # 3. 缓存未命中，创建新 Shape 并缓存
        new_offset = self.depth
        new_shape = Shape(self, prop_name, new_offset)
        
        self.transitions[prop_name] = new_shape
        Shape._transition_cache[cache_key] = new_shape
        return new_shape

# 全局空 Shape，作为所有对象的起点
EMPTY_SHAPE = Shape()
