import sys
import os

# 确保能找到 zhiai 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zhiai import ast_nodes as za_ast
from zhiai.builtins import BUILTINS

class JITCompiler:
    """致爱 JIT 转译器 — 将致爱 AST 转换为 Python 源代码"""
    
    def __init__(self):
        self.indent = 0
        self.code = []
        
    def emit(self, text):
        self.code.append("    " * self.indent + text)
        
    def compile(self, program):
        self.code = []
        self.indent = 0
        self.emit("# 致爱 JIT 自动生成的 Python 代码")
        self.emit("import sys")
        self.emit("")
        
        self.visit(program)
            
        return "\n".join(self.code)
    
    def visit(self, node):
        if node is None: return "None"
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name)
        return visitor(node)

    # ── 语句处理 ──

    def visit_Program(self, node):
        for stmt in node.statements:
            self.visit(stmt)

    def visit_VarDecl(self, node):
        val = self.visit(node.expr)
        self.emit(f"{node.name} = {val}")

    def visit_ConstDecl(self, node):
        val = self.visit(node.expr)
        self.emit(f"{node.name} = {val} # 常量")

    def visit_ExprStmt(self, node):
        # 赋值和复合赋值语句会自己调用 emit，这里不需要额外处理
        if isinstance(node.expr, (za_ast.Assign, za_ast.CompoundAssign)):
            self.visit(node.expr)
        else:
            val = self.visit(node.expr)
            self.emit(val)

    def visit_IfStmt(self, node):
        cond = self.visit(node.condition)
        self.emit(f"if {cond}:")
        self.indent += 1
        if not node.body: self.emit("pass")
        else:
            for stmt in node.body: self.visit(stmt)
        self.indent -= 1
        
        for elif_cond, elif_body in node.elifs:
            ec = self.visit(elif_cond)
            self.emit(f"elif {ec}:")
            self.indent += 1
            for stmt in elif_body: self.visit(stmt)
            self.indent -= 1
            
        if node.else_body:
            self.emit("else:")
            self.indent += 1
            for stmt in node.else_body: self.visit(stmt)
            self.indent -= 1

    def visit_WhileStmt(self, node):
        cond = self.visit(node.condition)
        self.emit(f"while {cond}:")
        self.indent += 1
        if not node.body: self.emit("pass")
        else:
            for stmt in node.body: self.visit(stmt)
        self.indent -= 1

    def visit_ForEachStmt(self, node):
        iterable = self.visit(node.iterable)
        self.emit(f"for {node.var_name} in {iterable}:")
        self.indent += 1
        if not node.body: self.emit("pass")
        else:
            for stmt in node.body: self.visit(stmt)
        self.indent -= 1

    def visit_ClassDef(self, node):
        self.emit(f"class {node.name}:")
        self.indent += 1
        if not node.methods:
            self.emit("pass")
        for method in node.methods:
            params = ["self"] + method.params
            self.emit(f"def {method.name}({', '.join(params)}):")
            self.indent += 1
            self.emit("这 = self")
            if not method.body: self.emit("pass")
            else:
                for stmt in method.body: self.visit(stmt)
            self.indent -= 1
        self.indent -= 1

    def visit_FuncDef(self, node):
        params = ", ".join(node.params)
        self.emit(f"def {node.name}({params}):")
        self.indent += 1
        if not node.body: self.emit("pass")
        else:
            for stmt in node.body: self.visit(stmt)
        self.indent -= 1

    def visit_ReturnStmt(self, node):
        val = self.visit(node.expr) if node.expr else "None"
        self.emit(f"return {val}")

    def visit_BreakStmt(self, node):
        self.emit("break")

    def visit_ContinueStmt(self, node):
        self.emit("continue")

    def visit_TryCatch(self, node):
        self.emit("try:")
        self.indent += 1
        for stmt in node.try_body: self.visit(stmt)
        self.indent -= 1
        self.emit(f"except Exception as {node.catch_var}:")
        self.indent += 1
        for stmt in node.catch_body: self.visit(stmt)
        self.indent -= 1

    # ── 表达式处理 ──

    def visit_NumberLit(self, node):
        return str(node.value)

    def visit_StringLit(self, node):
        return repr(node.value)

    def visit_BoolLit(self, node):
        return "True" if node.value else "False"

    def visit_NullLit(self, node):
        return "None"

    def visit_ArrayLit(self, node):
        elements = [self.visit(e) for e in node.elements]
        return "[" + ", ".join(elements) + "]"

    def visit_ObjectLit(self, node):
        pairs = [f"{self.visit(k)}: {self.visit(v)}" for k, v in node.pairs]
        return "{" + ", ".join(pairs) + "}"

    def visit_Identifier(self, node):
        return node.name

    def visit_UnaryOp(self, node):
        op_map = {"-": "-", "NOT": "not "}
        op = op_map.get(node.op, node.op)
        return f"({op}{self.visit(node.operand)})"

    def visit_BinaryOp(self, node):
        op_map = {
            "+": "+", "-": "-", "*": "*", "/": "/", "%": "%", "**": "**",
            "==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">=",
            "并且": " and ", "或者": " or ", "AND": " and ", "OR": " or "
        }
        op = op_map.get(node.op, node.op)
        return f"({self.visit(node.left)} {op} {self.visit(node.right)})"

    def visit_target(self, node):
        """生成赋值目标字符串"""
        if isinstance(node, za_ast.Identifier):
            return node.name
        if isinstance(node, za_ast.IndexAccess):
            return f"{self.visit(node.obj)}[{self.visit(node.index)}]"
        if isinstance(node, za_ast.PropertyAccess):
            # 修复 Bug #8: 返回一个兼容 getattr 的目标描述
            return f"getattr({self.visit(node.obj)}, '{node.prop}')"
        return "unknown_target"

    def visit_Assign(self, node):
        if isinstance(node.target, za_ast.PropertyAccess):
            # 修复 Bug #8: 属性赋值逻辑
            obj = self.visit(node.target.obj)
            prop = node.target.prop
            val = self.visit(node.value)
            self.emit(f"_za_set_prop({obj}, '{prop}', {val})")
        elif isinstance(node.target, za_ast.Identifier) and self.indent > 0:
            # 修复 Bug #12: 简单的闭包变量修改支持 (尝试自动 nonlocal)
            # 注意：这里需要更复杂的 scope 检查，目前是预防性尝试
            self.emit(f"try: nonlocal {node.target.name}")
            self.emit(f"except: pass")
            target = self.visit_target(node.target)
            val = self.visit(node.value)
            self.emit(f"{target} = {val}")
        else:
            target = self.visit_target(node.target)
            val = self.visit(node.value)
            self.emit(f"{target} = {val}")

    def visit_CompoundAssign(self, node):
        if isinstance(node.target, za_ast.PropertyAccess):
            obj = self.visit(node.target.obj)
            prop = node.target.prop
            val = self.visit(node.value)
            # 简单实现：obj.prop = obj.prop + val
            self.emit(f"_za_set_prop({obj}, '{prop}', _za_get_prop({obj}, '{prop}') {node.op} {val})")
        else:
            target = self.visit_target(node.target)
            val = self.visit(node.value)
            self.emit(f"{target} {node.op}= {val}")

    def visit_Call(self, node):
        callee = self.visit(node.callee)
        args = [self.visit(a) for a in node.args]
        return f"{callee}({', '.join(args)})"

    def visit_IndexAccess(self, node):
        return f"{self.visit(node.obj)}[{self.visit(node.index)}]"

    def visit_PropertyAccess(self, node):
        return f"_za_get_prop({self.visit(node.obj)}, '{node.prop}')"

    def visit_MethodCall(self, node):
        obj = self.visit(node.obj)
        args = [self.visit(a) for a in node.args]
        return f"_za_method_call({obj}, '{node.method}', {', '.join(args)})"

    def visit_AnonymousFunc(self, node):
        # Python 的 lambda 只能是表达式，简单实现
        return f"(lambda {', '.join(node.params)}: {self.visit(node.body[0].expr) if len(node.body)==1 and isinstance(node.body[0], za_ast.ReturnStmt) else 'None'})"

def exec_jit(ast_program):
    """编译并执行 JIT 代码"""
    compiler = JITCompiler()
    py_source = compiler.compile(ast_program)
    
    # 准备执行环境
    env = {}
    env.update(BUILTINS)
    
    # JIT 运行时助手
    def _za_get_prop(obj, prop):
        if isinstance(obj, dict): return obj.get(prop)
        return getattr(obj, prop, None)
    
    def _za_set_prop(obj, prop, val):
        if isinstance(obj, dict): obj[prop] = val
        else: setattr(obj, prop, val)
        return val

    def _za_method_call(obj, method, *args):
        if isinstance(obj, dict): return obj[method](*args)
        return getattr(obj, method)(*args)

    env["_za_get_prop"] = _za_get_prop
    env["_za_set_prop"] = _za_set_prop
    env["_za_method_call"] = _za_method_call

    # 执行
    try:
        exec(py_source, env)
    except Exception as e:
        import traceback
        print("JIT 运行时错误:")
        traceback.print_exc()
