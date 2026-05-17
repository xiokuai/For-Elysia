"""AST 节点定义"""


class Node:
    """所有AST节点的基类"""
    pass


# ── 程序 ──────────────────────────────────────────────────────────────

class Program(Node):
    def __init__(self, statements):
        self.statements = statements


# ── 语句 ──────────────────────────────────────────────────────────────

class VarDecl(Node):
    """让 x = 值"""
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr


class ConstDecl(Node):
    """常量 x = 值"""
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr


class ExprStmt(Node):
    """表达式语句（仅执行，丢弃结果）"""
    def __init__(self, expr):
        self.expr = expr


class IfStmt(Node):
    """如果 ... 则 ... 否则如果 ... 否则 ... 结束"""
    def __init__(self, condition, body, elifs=None, else_body=None):
        self.condition = condition
        self.body = body
        self.elifs = elifs or []  # list of (condition, body)
        self.else_body = else_body


class WhileStmt(Node):
    """当 条件 时 ... 结束"""
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body


class ForStmt(Node):
    """循环 变量 从 起 到 终 步长 N ... 结束"""
    def __init__(self, var_name, start, end, step, body):
        self.var_name = var_name
        self.start = start
        self.end = end
        self.step = step
        self.body = body


class ForEachStmt(Node):
    """对于 每个 元素 在 数组 中 ... 结束"""
    def __init__(self, var_name, iterable, body):
        self.var_name = var_name
        self.iterable = iterable
        self.body = body


class FuncDef(Node):
    """函数 名称(参数) ... 结束"""
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body


class ReturnStmt(Node):
    """返回 表达式"""
    def __init__(self, expr):
        self.expr = expr


class BreakStmt(Node):
    """中断"""
    pass


class ContinueStmt(Node):
    """继续"""
    pass


class TryCatch(Node):
    """尝试 ... 捕获 变量 ... 结束"""
    def __init__(self, try_body, catch_var, catch_body):
        self.try_body = try_body
        self.catch_var = catch_var
        self.catch_body = catch_body


# ── 表达式 ────────────────────────────────────────────────────────────

class NumberLit(Node):
    """数字字面量"""
    def __init__(self, value):
        self.value = value


class StringLit(Node):
    """字符串字面量"""
    def __init__(self, value):
        self.value = value


class BoolLit(Node):
    """布尔字面量：真 / 假"""
    def __init__(self, value):
        self.value = value


class NullLit(Node):
    """空"""
    pass


class ArrayLit(Node):
    """[元素, ...]"""
    def __init__(self, elements):
        self.elements = elements


class ObjectLit(Node):
    """{"键": 值, ...}"""
    def __init__(self, pairs):
        self.pairs = pairs  # list of (key_expr, value_expr)


class Identifier(Node):
    """变量名"""
    def __init__(self, name):
        self.name = name


class UnaryOp(Node):
    """一元运算: -值, 非值"""
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand


class BinaryOp(Node):
    """二元运算: a + b, a == b, a 并且 b"""
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right


class Assign(Node):
    """赋值: x = 值, arr[0] = 值, obj.属性 = 值"""
    def __init__(self, target, value):
        self.target = target
        self.value = value


class CompoundAssign(Node):
    """复合赋值: x += 值, arr[0] -= 值（目标只求值一次）"""
    def __init__(self, target, op, value):
        self.target = target
        self.op = op        # "+", "-", "*", "/"
        self.value = value


class Call(Node):
    """函数调用: 函数名(参数...)"""
    def __init__(self, callee, args, is_async=False):
        self.callee = callee
        self.args = args
        self.is_async = is_async


class IndexAccess(Node):
    """索引访问: 数组[索引]"""
    def __init__(self, obj, index):
        self.obj = obj
        self.index = index


class PropertyAccess(Node):
    """属性访问: 对象.属性"""
    def __init__(self, obj, prop):
        self.obj = obj
        self.prop = prop


class MethodCall(Node):
    """方法调用: 对象.方法(参数...)"""
    def __init__(self, obj, method, args):
        self.obj = obj
        self.method = method
        self.args = args


class AnonymousFunc(Node):
    """匿名函数: 函数(参数) 返回 表达式 结束"""
    def __init__(self, params, body):
        self.params = params
        self.body = body


class ClassDef(Node):
    """类 名称 ... 结束"""
    def __init__(self, name, methods):
        self.name = name
        self.methods = methods # list of FuncDef


class DeferStmt(Node):
    """延迟 表达式"""
    def __init__(self, expr):
        self.expr = expr


class AsyncFuncDef(FuncDef):
    """异步函数定义"""
    pass


class AwaitExpr(Node):
    """等待 表达式"""
    def __init__(self, expr):
        self.expr = expr

