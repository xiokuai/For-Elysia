"""致爱解释器 — 树遍历执行引擎"""

from . import ast_nodes as ast
from .builtins import BUILTINS, ARRAY_METHODS, STRING_METHODS, ZhiAiError


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class Environment:
    """变量作用域"""

    def __init__(self, parent=None):
        self.vars = {}
        self.consts = set()
        self.parent = parent

    def define(self, name, value):
        self.vars[name] = value

    def define_const(self, name, value):
        self.vars[name] = value
        self.consts.add(name)

    def get(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise RuntimeError(f"未定义的变量: '{name}'")

    def set(self, name, value):
        if name in self.vars:
            if name in self.consts:
                raise RuntimeError(f"无法修改常量: '{name}'")
            self.vars[name] = value
            return
        if self.parent:
            self.parent.set(name, value)
            return
        raise RuntimeError(f"未定义的变量: '{name}'")

    def has(self, name):
        if name in self.vars:
            return True
        if self.parent:
            return self.parent.has(name)
        return False


class Instance:
    """致爱类实例"""
    def __init__(self, klass):
        self.klass = klass
        self.fields = {}

    def get_prop(self, name):
        if name in self.fields:
            return self.fields[name]
        if name in self.klass.methods:
            return self.klass.methods[name]
        return None

    def set_prop(self, name, value):
        self.fields[name] = value

    def __repr__(self):
        return f"<实例 {self.klass.name}>"


class Function:
    """用户定义的函数"""

    def __init__(self, name, params, body, closure, interpreter=None):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.interpreter = interpreter

    def __repr__(self):
        return f"<函数 {self.name}>" if self.name else "<匿名函数>"

    def __call__(self, *args):
        """使函数可直接调用（用于内置方法如筛选、连接等）"""
        if not self.interpreter:
            raise RuntimeError("函数未绑定解释器")
        if len(args) != len(self.params):
            raise RuntimeError(
                f"函数 '{self.name or '匿名'}' 期望 {len(self.params)} 个参数，"
                f"但得到 {len(args)} 个"
            )
        func_env = Environment(self.closure)
        for param, arg in zip(self.params, args):
            func_env.define(param, arg)
        
        # 准备延迟执行栈
        self.interpreter.defer_stacks.append([])
        try:
            self.interpreter.exec_stmts(self.body, func_env)
            return None
        except ReturnSignal as ret:
            return ret.value
        finally:
            # 执行延迟任务
            defers = self.interpreter.defer_stacks.pop() if self.interpreter.defer_stacks else []
            for expr, env in reversed(defers):
                self.interpreter.eval(expr, env)


class Class:
    """致爱类定义"""
    def __init__(self, name, methods, interpreter):
        self.name = name
        self.methods = methods # 这里的 methods 是 Function 对象映射
        self.interpreter = interpreter

    def __call__(self, *args):
        # 实例化类
        instance = Instance(self)
        # 检查是否有构造函数
        if "构造" in self.methods:
            ctor = self.methods["构造"]
            # 绑定 '这' (this) 到实例
            func_env = Environment(ctor.closure)
            func_env.define("这", instance)
            for param, arg in zip(ctor.params, args):
                func_env.define(param, arg)
            
            self.interpreter.defer_stacks.append([])
            try:
                self.interpreter.exec_stmts(ctor.body, func_env)
            except ReturnSignal:
                pass
            finally:
                defers = self.interpreter.defer_stacks.pop() if self.interpreter.defer_stacks else []
                for expr, env in reversed(defers):
                    self.interpreter.eval(expr, env)
        return instance

    def __repr__(self):
        return f"<类 {self.name}>"


class Interpreter:
    """解释器"""

    def __init__(self):
        self.global_env = Environment()
        # 注册内置函数
        for name, func in BUILTINS.items():
            self.global_env.define(name, func)
            
        self.global_env.define("导入", self._builtin_import)
        self.defer_stacks = [[]] # 顶级延迟栈

    def _builtin_import(self, module_path):
        import os
        from zhiai.lexer import tokenize
        from zhiai.parser import parse
        
        if not os.path.exists(module_path):
            if os.path.exists(module_path + ".za"):
                module_path += ".za"
            elif os.path.exists(module_path + ".zab"):
                # 如果只有 .zab，退化为启动 VM
                try:
                    from zhiai._fastvm import VM
                except ImportError:
                    from zhiai.vm import VM
                sub_vm = VM()
                sub_vm.load_file(module_path + ".zab")
                sub_vm.run()
                exports = {}
                for k, v in sub_vm.global_env.vars.items():
                    if k not in BUILTINS and k != "导入":
                        exports[k] = v
                return exports
            else:
                raise RuntimeError(f"导入失败: 找不到模块 '{module_path}'")
                
        # 加载 .za
        if module_path.endswith(".zab"):
            try:
                from zhiai._fastvm import VM
            except ImportError:
                from zhiai.vm import VM
            sub_vm = VM()
            sub_vm.load_file(module_path)
            sub_vm.run()
            exports = {}
            for k, v in sub_vm.global_env.vars.items():
                if k not in BUILTINS and k != "导入":
                    exports[k] = v
            return exports

        with open(module_path, "r", encoding="utf-8") as f:
            src = f.read()
        tokens = tokenize(src, module_path)
        program = parse(tokens)
        sub_interp = Interpreter()
        sub_interp.run(program)
        exports = {}
        for k, v in sub_interp.global_env.vars.items():
            if k not in BUILTINS and k != "导入":
                exports[k] = v
        return exports

    def run(self, program):
        """执行程序"""
        try:
            self.exec_stmts(program.statements, self.global_env)
        finally:
            if self.defer_stacks:
                defers = self.defer_stacks.pop()
                for expr, env in reversed(defers):
                    self.eval(expr, env)

    def exec_stmts(self, stmts, env):
        """执行语句列表"""
        for stmt in stmts:
            res = self.exec_stmt(stmt, env)
            if res is not None:
                return res
        return None

    def exec_stmt(self, stmt, env):
        """执行单条语句"""
        if isinstance(stmt, ast.VarDecl):
            value = self.eval(stmt.expr, env)
            env.define(stmt.name, value)

        elif isinstance(stmt, ast.ConstDecl):
            value = self.eval(stmt.expr, env)
            env.define_const(stmt.name, value)

        elif isinstance(stmt, ast.ExprStmt):
            self.eval(stmt.expr, env)

        elif isinstance(stmt, ast.IfStmt):
            condition = self.eval(stmt.condition, env)
            if self.is_truthy(condition):
                return self.exec_stmts(stmt.body, env)
            else:
                executed = False
                for elif_cond, elif_body in stmt.elifs:
                    if self.is_truthy(self.eval(elif_cond, env)):
                        res = self.exec_stmts(elif_body, env)
                        if res is not None: return res
                        executed = True
                        break
                if not executed and stmt.else_body:
                    return self.exec_stmts(stmt.else_body, env)

        elif isinstance(stmt, ast.WhileStmt):
            while self.is_truthy(self.eval(stmt.condition, env)):
                try:
                    res = self.exec_stmts(stmt.body, env)
                    if res is not None: return res
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue

        elif isinstance(stmt, ast.ForStmt):
            start = self.eval(stmt.start, env)
            end = self.eval(stmt.end, env)
            step = self.eval(stmt.step, env) if stmt.step else 1
            i = start
            first = True
            if step > 0:
                while i <= end:
                    if first:
                        env.define(stmt.var_name, i)
                        first = False
                    else:
                        env.set(stmt.var_name, i)
                    try:
                        res = self.exec_stmts(stmt.body, env)
                        if res is not None: return res
                    except BreakSignal:
                        break
                    except ContinueSignal:
                        pass
                    i += step
            elif step < 0:
                while i >= end:
                    if first:
                        env.define(stmt.var_name, i)
                        first = False
                    else:
                        env.set(stmt.var_name, i)
                    try:
                        res = self.exec_stmts(stmt.body, env)
                        if res is not None: return res
                    except BreakSignal:
                        break
                    except ContinueSignal:
                        pass
                    i += step

        elif isinstance(stmt, ast.ForEachStmt):
            iterable = self.eval(stmt.iterable, env)
            if isinstance(iterable, dict):
                items = list(iterable.keys())
            elif isinstance(iterable, (list, str)):
                items = iterable
            else:
                raise RuntimeError("'对于 每个' 需要一个数组、字符串或对象")
            for item in items:
                env.define(stmt.var_name, item)
                try:
                    res = self.exec_stmts(stmt.body, env)
                    if res is not None: return res
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue

        elif isinstance(stmt, ast.FuncDef):
            func = Function(stmt.name, stmt.params, stmt.body, env, self)
            env.define(stmt.name, func)

        elif isinstance(stmt, ast.ReturnStmt):
            value = self.eval(stmt.expr, env) if stmt.expr else None
            raise ReturnSignal(value)

        elif isinstance(stmt, ast.BreakStmt):
            raise BreakSignal()

        elif isinstance(stmt, ast.ContinueStmt):
            raise ContinueSignal()

        elif isinstance(stmt, ast.TryCatch):
            try:
                return self.exec_stmts(stmt.try_body, env)
            except (ReturnSignal, BreakSignal, ContinueSignal):
                raise
            except Exception as e:
                catch_env = Environment(env)
                catch_env.define(stmt.catch_var, str(e))
                return self.exec_stmts(stmt.catch_body, catch_env)

        elif isinstance(stmt, ast.DeferStmt):
            self.defer_stacks[-1].append((stmt.expr, env))

        elif isinstance(stmt, ast.ClassDef):
            methods = {}
            klass = Class(stmt.name, methods, self)
            env.define(stmt.name, klass)
            for m in stmt.methods:
                methods[m.name] = Function(m.name, m.params, m.body, env, self)

        elif isinstance(stmt, ast.Program):
            return self.exec_stmts(stmt.statements, env)

        else:
            raise RuntimeError(f"未知的语句类型: {type(stmt).__name__}")
        return None

    def eval(self, node, env):
        """求值表达式"""
        # 字面量
        if isinstance(node, ast.NumberLit):
            return node.value
        if isinstance(node, ast.StringLit):
            return node.value
        if isinstance(node, ast.BoolLit):
            return node.value
        if isinstance(node, ast.NullLit):
            return None

        # 数组字面量
        if isinstance(node, ast.ArrayLit):
            return [self.eval(e, env) for e in node.elements]

        # 对象字面量
        if isinstance(node, ast.ObjectLit):
            obj = {}
            for key_expr, val_expr in node.pairs:
                key = self.eval(key_expr, env)
                if not isinstance(key, str):
                    raise RuntimeError("对象键必须是字符串")
                obj[key] = self.eval(val_expr, env)
            return obj

        # 标识符
        if isinstance(node, ast.Identifier):
            return env.get(node.name)

        # 一元运算
        if isinstance(node, ast.UnaryOp):
            operand = self.eval(node.operand, env)
            if node.op == "-":
                if isinstance(operand, (int, float)):
                    return -operand
                raise RuntimeError(f"无法对 {type(operand).__name__} 取负")
            if node.op in ("非", "!"):
                return not self.is_truthy(operand)
            raise RuntimeError(f"未知的一元运算符: {node.op}")

        # 二元运算
        if isinstance(node, ast.BinaryOp):
            return self.eval_binary(node, env)

        # 赋值
        if isinstance(node, ast.Assign):
            return self.eval_assign(node, env)

        # 复合赋值
        if isinstance(node, ast.CompoundAssign):
            return self.eval_compound_assign(node, env)

        # 函数调用
        if isinstance(node, ast.Call):
            return self.eval_call(node, env)

        # 索引访问
        if isinstance(node, ast.IndexAccess):
            return self.eval_index(node, env)

        # 属性访问
        if isinstance(node, ast.PropertyAccess):
            return self.eval_property(node, env)

        # 方法调用
        if isinstance(node, ast.MethodCall):
            return self.eval_method(node, env)

        # 匿名函数
        if isinstance(node, ast.AnonymousFunc):
            return Function(None, node.params, node.body, env, self)

        elif isinstance(node, ast.AwaitExpr):
            val = self.eval(node.expr, env)
            if hasattr(val, "result"):
                return val.result()
            return val

        raise RuntimeError(f"未知的表达式类型: {type(node).__name__}")

    def eval_binary(self, node, env):
        """求值二元运算"""
        left = self.eval(node.left, env)
        op = node.op

        # 短路求值
        if op in ("并且", "&&"):
            if not self.is_truthy(left):
                return left
            return self.eval(node.right, env)
        if op in ("或者", "||"):
            if self.is_truthy(left):
                return left
            return self.eval(node.right, env)

        right = self.eval(node.right, env)

        # 算术
        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return self.to_str(left) + self.to_str(right)
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise RuntimeError("除以零")
            if isinstance(left, int) and isinstance(right, int) and left % right == 0:
                return left // right
            return left / right
        if op == "%":
            if right == 0:
                raise RuntimeError("除以零")
            return left % right
        if op == "**":
            return left ** right

        # 比较
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right

        raise RuntimeError(f"未知的运算符: {op}")

    def eval_assign(self, node, env):
        """求值赋值"""
        value = self.eval(node.value, env)

        if isinstance(node.target, ast.Identifier):
            env.set(node.target.name, value)
        elif isinstance(node.target, ast.IndexAccess):
            obj = self.eval(node.target.obj, env)
            index = self.eval(node.target.index, env)
            if isinstance(obj, list):
                obj[int(index)] = value
            elif isinstance(obj, dict):
                obj[index] = value
            else:
                raise RuntimeError(f"无法索引赋值: {type(obj).__name__}")
        elif isinstance(node.target, ast.PropertyAccess):
            obj = self.eval(node.target.obj, env)
            if isinstance(obj, Instance):
                obj.set_prop(node.target.prop, value)
            elif isinstance(obj, dict):
                obj[node.target.prop] = value
            elif hasattr(obj, node.target.prop):
                setattr(obj, node.target.prop, value)
            else:
                raise RuntimeError(f"无法属性赋值: {type(obj).__name__}")
        else:
            raise RuntimeError("无效的赋值目标")

        return value

    def eval_compound_assign(self, node, env):
        """求值复合赋值"""
        inc = self.eval(node.value, env)
        op = node.op

        if isinstance(node.target, ast.Identifier):
            old = env.get(node.target.name)
            new_val = self._apply_op(old, op, inc)
            env.set(node.target.name, new_val)
            return new_val

        if isinstance(node.target, ast.IndexAccess):
            obj = self.eval(node.target.obj, env)
            index = self.eval(node.target.index, env)
            if isinstance(obj, list):
                old = obj[int(index)]
                new_val = self._apply_op(old, op, inc)
                obj[int(index)] = new_val
                return new_val
            if isinstance(obj, dict):
                old = obj.get(index)
                new_val = self._apply_op(old, op, inc)
                obj[index] = new_val
                return new_val
            raise RuntimeError(f"无法索引赋值: {type(obj).__name__}")

        if isinstance(node.target, ast.PropertyAccess):
            obj = self.eval(node.target.obj, env)
            if isinstance(obj, Instance):
                old = obj.get_prop(node.target.prop)
                new_val = self._apply_op(old, op, inc)
                obj.set_prop(node.target.prop, new_val)
                return new_val
            if isinstance(obj, dict):
                old = obj.get(node.target.prop)
                new_val = self._apply_op(old, op, inc)
                obj[node.target.prop] = new_val
                return new_val
            raise RuntimeError(f"无法属性赋值: {type(obj).__name__}")

        raise RuntimeError("无效的复合赋值目标")

    def _apply_op(self, left, op, right):
        """执行二元运算"""
        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return self.to_str(left) + self.to_str(right)
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise RuntimeError("除以零")
            if isinstance(left, int) and isinstance(right, int) and left % right == 0:
                return left // right
            return left / right
        raise RuntimeError(f"未知的运算符: {op}")

    def eval_call(self, node, env):
        """求值函数调用"""
        callee = self.eval(node.callee, env)
        args = [self.eval(a, env) for a in node.args]

        if node.is_async:
            import concurrent.futures
            from .builtins import wrap_callable
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            wrapped = wrap_callable(callee)
            return executor.submit(wrapped, *args)

        if isinstance(callee, (Function, Class)):
            return callee(*args)

        if callable(callee):
            try:
                from .builtins import wrap_callable
                args = [wrap_callable(a) for a in args]
                return callee(*args)
            except TypeError as e:
                raise RuntimeError(f"调用错误: {e}")

        raise RuntimeError(f"无法调用: {type(callee).__name__}")

    def eval_index(self, node, env):
        """求值索引访问"""
        obj = self.eval(node.obj, env)
        index = self.eval(node.index, env)

        if isinstance(obj, list):
            if not isinstance(index, int):
                raise RuntimeError("数组索引必须是整数")
            if index < 0:
                index += len(obj)
            if index < 0 or index >= len(obj):
                raise RuntimeError(f"索引越界: {index}")
            return obj[index]
        if isinstance(obj, dict):
            if index in obj:
                return obj[index]
            raise RuntimeError(f"键不存在: '{index}'")
        if isinstance(obj, str):
            if not isinstance(index, int):
                raise RuntimeError("字符串索引必须是整数")
            if index < 0:
                index += len(obj)
            if index < 0 or index >= len(obj):
                raise RuntimeError(f"索引越界: {index}")
            return obj[index]

        raise RuntimeError(f"无法索引: {type(obj).__name__}")

    def eval_property(self, node, env):
        """求值属性访问"""
        obj = self.eval(node.obj, env)
        prop = node.prop

        if isinstance(obj, Instance):
            val = obj.get_prop(prop)
            if isinstance(val, Function):
                # 自动绑定 '这'
                bound_env = Environment(val.closure)
                bound_env.define("这", obj)
                return Function(val.name, val.params, val.body, bound_env, self)
            return val

        if isinstance(obj, list) and prop == "长度":
            return len(obj)
        if isinstance(obj, str) and prop == "长度":
            return len(obj)
        if isinstance(obj, dict):
            if prop in obj:
                return obj[prop]
            return None

        if isinstance(obj, list) and prop in ARRAY_METHODS:
            return lambda *args: ARRAY_METHODS[prop](obj, *args)
        if isinstance(obj, str) and prop in STRING_METHODS:
            return lambda *args: STRING_METHODS[prop](obj, *args)

        if hasattr(obj, prop):
            val = getattr(obj, prop)
            return val

        raise RuntimeError(f"类型 {type(obj).__name__} 没有属性 '{prop}'")

    def eval_method(self, node, env):
        """求值方法调用"""
        obj = self.eval(node.obj, env)
        method = node.method
        args = [self.eval(a, env) for a in node.args]

        if isinstance(obj, Instance):
            func = obj.get_prop(method)
            if isinstance(func, Function):
                # 手动绑定并调用
                bound_env = Environment(func.closure)
                bound_env.define("这", obj)
                bound_func = Function(func.name, func.params, func.body, bound_env, self)
                return bound_func(*args)
            raise RuntimeError(f"实例没有方法 '{method}'")

        if isinstance(obj, list):
            if method in ARRAY_METHODS:
                return ARRAY_METHODS[method](obj, *args)
            if method == "长度":
                return len(obj)
            raise RuntimeError(f"数组没有方法 '{method}'")

        if isinstance(obj, str):
            if method in STRING_METHODS:
                return STRING_METHODS[method](obj, *args)
            if method == "长度":
                return len(obj)
            raise RuntimeError(f"字符串没有方法 '{method}'")

        if isinstance(obj, dict):
            if method in obj:
                func = obj[method]
                if callable(func):
                    return func(*args)
            raise RuntimeError(f"对象没有方法 '{method}'")

        if hasattr(obj, method):
            func = getattr(obj, method)
            if callable(func):
                return func(*args)

        raise RuntimeError(f"类型 {type(obj).__name__} 没有方法 '{method}'")

    def is_truthy(self, value):
        """判断值是否为真"""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, list):
            return len(value) > 0
        if isinstance(value, dict):
            return len(value) > 0
        return True

    def to_str(self, value):
        """转换为字符串"""
        if value is None:
            return "空"
        if isinstance(value, bool):
            return "真" if value else "假"
        if isinstance(value, float):
            if value == int(value):
                return str(int(value))
        return str(value)
