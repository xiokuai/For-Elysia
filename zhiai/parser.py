"""致爱语法分析器 — 将token流构建为AST"""

from .lexer import TT, Token
from . import ast_nodes as ast


class ParseError(Exception):
    def __init__(self, message, token):
        super().__init__(f"语法错误 行{token.line}: {message}")
        self.token = token


class Parser:
    """递归下降语法分析器"""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def is_at_end(self):
        return self.peek().type == TT.EOF

    def check(self, tt):
        return self.peek().type == tt

    def expect(self, tt, message=None):
        tok = self.peek()
        if tok.type != tt:
            msg = message or f"期望 {tt.name}，但得到 {tok.type.name} '{tok.value}'"
            raise ParseError(msg, tok)
        return self.advance()

    def match(self, *types):
        if self.peek().type in types:
            return self.advance()
        return None

    def error(self, message=None):
        tok = self.peek()
        msg = message or f"意外的token: {tok.type.name} '{tok.value}'"
        raise ParseError(msg, tok)

    # ── 程序入口 ──────────────────────────────────────────────────────

    def parse(self):
        stmts = []
        while not self.is_at_end():
            stmts.append(self.parse_stmt())
        return ast.Program(stmts)

    # ── 语句 ──────────────────────────────────────────────────────────

    def parse_stmt(self):
        tok = self.peek()

        if tok.type == TT.LET:
            return self.parse_let()
        if tok.type == TT.CONST:
            return self.parse_const()
        if tok.type == TT.IF:
            return self.parse_if()
        if tok.type == TT.WHILE:
            return self.parse_while()
        if tok.type == TT.FOR:
            return self.parse_for()
        if tok.type == TT.FUNC:
            return self.parse_func_def()
        if tok.type == TT.RETURN:
            return self.parse_return()
        if tok.type == TT.BREAK:
            self.advance()
            return ast.BreakStmt()
        if tok.type == TT.CONTINUE:
            self.advance()
            return ast.ContinueStmt()
        if tok.type == TT.TRY:
            return self.parse_try_catch()
        if tok.type == TT.IDENTIFIER and tok.value == "类":
            return self.parse_class()

        # 表达式语句
        expr = self.parse_expr()

        # 赋值: x = 值, arr[i] = 值, obj.p = 值, x += 值 等
        if self.check(TT.EQ):
            self.advance()
            value = self.parse_expr()
            return ast.ExprStmt(ast.Assign(expr, value))

        # 复合赋值
        if self.peek().type in (TT.PLUS_EQ, TT.MINUS_EQ, TT.STAR_EQ, TT.SLASH_EQ):
            op_tok = self.advance()
            op_map = {TT.PLUS_EQ: "+", TT.MINUS_EQ: "-", TT.STAR_EQ: "*", TT.SLASH_EQ: "/"}
            value = self.parse_expr()
            return ast.ExprStmt(ast.CompoundAssign(expr, op_map[op_tok.type], value))

        return ast.ExprStmt(expr)

    def parse_let(self):
        self.expect(TT.LET)
        name = self.expect(TT.IDENTIFIER, "期望变量名").value
        self.expect(TT.EQ, "期望 '='")
        expr = self.parse_expr()
        return ast.VarDecl(name, expr)

    def parse_const(self):
        self.expect(TT.CONST)
        name = self.expect(TT.IDENTIFIER, "期望常量名").value
        self.expect(TT.EQ, "期望 '='")
        expr = self.parse_expr()
        return ast.ConstDecl(name, expr)

    def parse_if(self):
        self.expect(TT.IF)
        condition = self.parse_expr()
        # 支持 "如果 条件 则" 中的 "则"
        if self.check(TT.IDENTIFIER) and self.peek().value == "则":
            self.advance()
        body = self.parse_block()

        elifs = []
        while self.check(TT.ELIF):
            self.advance()
            elif_cond = self.parse_expr()
            if self.check(TT.IDENTIFIER) and self.peek().value == "则":
                self.advance()
            elif_body = self.parse_block()
            elifs.append((elif_cond, elif_body))

        else_body = None
        if self.check(TT.ELSE):
            self.advance()
            else_body = self.parse_block()

        self.expect(TT.END, "期望 '结束'")
        return ast.IfStmt(condition, body, elifs, else_body)

    def parse_while(self):
        self.expect(TT.WHILE)
        condition = self.parse_expr()
        if self.check(TT.IDENTIFIER) and self.peek().value == "时":
            self.advance()
        body = self.parse_block()
        self.expect(TT.END, "期望 '结束'")
        return ast.WhileStmt(condition, body)

    def parse_for(self):
        self.expect(TT.FOR)

        # 对于 每个 元素 在 数组 中
        if self.check(TT.EACH):
            self.expect(TT.EACH)
            var_name = self.expect(TT.IDENTIFIER, "期望变量名").value
            self.expect(TT.IN, "期望 '在'")
            iterable = self.parse_expr()
            self.expect(TT.MID, "期望 '中'")
            body = self.parse_block()
            self.expect(TT.END, "期望 '结束'")
            return ast.ForEachStmt(var_name, iterable, body)

        # 循环 变量 从 X 到 Y [步长 Z]
        var_name = self.expect(TT.IDENTIFIER, "期望循环变量名").value

        if self.check(TT.FROM):
            self.expect(TT.FROM)
            start = self.parse_expr()
            self.expect(TT.TO, "期望 '到'")
            end = self.parse_expr()
            step = None
            if self.check(TT.STEP):
                self.advance()
                step = self.parse_expr()
            body = self.parse_block()
            self.expect(TT.END, "期望 '结束'")
            return ast.ForStmt(var_name, start, end, step, body)
        else:
            self.error("期望 '从'")

    def parse_func_def(self):
        self.expect(TT.FUNC)
        name = self.expect(TT.IDENTIFIER, "期望函数名").value
        self.expect(TT.LPAREN, "期望 '('")
        params = self.parse_params()
        self.expect(TT.RPAREN, "期望 ')'")
        body = self.parse_block()
        self.expect(TT.END, "期望 '结束'")
        return ast.FuncDef(name, params, body)

    def parse_params(self):
        params = []
        if not self.check(TT.RPAREN):
            params.append(self.expect(TT.IDENTIFIER, "期望参数名").value)
            while self.check(TT.COMMA):
                self.advance()
                params.append(self.expect(TT.IDENTIFIER, "期望参数名").value)
        return params

    def parse_return(self):
        self.expect(TT.RETURN)
        expr = self.parse_expr() if not self.is_at_end() and not self.check(TT.END) else None
        return ast.ReturnStmt(expr)

    def parse_try_catch(self):
        self.expect(TT.TRY)
        try_body = self.parse_block()
        self.expect(TT.CATCH, "期望 '捕获'")
        catch_var = self.expect(TT.IDENTIFIER, "期望变量名").value
        catch_body = self.parse_block()
        self.expect(TT.END, "期望 '结束'")
        return ast.TryCatch(try_body, catch_var, catch_body)

    def parse_block(self):
        """解析代码块（一系列语句，直到遇到结束关键字）"""
        stmts = []
        stop_types = {TT.END, TT.ELIF, TT.ELSE, TT.CATCH, TT.EOF}
        while not self.is_at_end() and self.peek().type not in stop_types:
            stmts.append(self.parse_stmt())
        return stmts

    # ── 表达式 ────────────────────────────────────────────────────────

    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.check(TT.OR) or self.check(TT.OR_OR):
            op = self.advance().value
            right = self.parse_and()
            left = ast.BinaryOp(left, op, right)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.check(TT.AND) or self.check(TT.AND_AND):
            op = self.advance().value
            right = self.parse_not()
            left = ast.BinaryOp(left, op, right)
        return left

    def parse_not(self):
        if self.check(TT.NOT) or self.check(TT.NOT_BANG):
            op = self.advance().value
            operand = self.parse_not()
            return ast.UnaryOp(op, operand)
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_addition()
        while self.peek().type in (TT.EQEQ, TT.NEQ, TT.LT, TT.GT, TT.LTE, TT.GTE):
            op = self.advance().value
            right = self.parse_addition()
            left = ast.BinaryOp(left, op, right)
        return left

    def parse_addition(self):
        left = self.parse_multiplication()
        while self.peek().type in (TT.PLUS, TT.MINUS):
            op = self.advance().value
            right = self.parse_multiplication()
            left = ast.BinaryOp(left, op, right)
        return left

    def parse_multiplication(self):
        left = self.parse_power()
        while self.peek().type in (TT.STAR, TT.SLASH, TT.PERCENT):
            op = self.advance().value
            right = self.parse_power()
            left = ast.BinaryOp(left, op, right)
        return left

    def parse_power(self):
        left = self.parse_unary()
        if self.check(TT.POWER):
            self.advance()
            right = self.parse_power()  # 右结合
            left = ast.BinaryOp(left, "**", right)
        return left

    def parse_unary(self):
        if self.check(TT.MINUS):
            self.advance()
            operand = self.parse_unary()
            return ast.UnaryOp("-", operand)
        return self.parse_call_or_access()

    def parse_arrow_func_from_ident(self, ident_tok):
        """检测到 ident => 后构建单参数箭头函数"""
        self.advance()  # consume =>
        body_expr = self.parse_expr()
        return ast.AnonymousFunc([ident_tok.value], [ast.ReturnStmt(body_expr)])

    def parse_call_or_access(self):
        """解析函数调用、属性访问、索引访问"""
        expr = self.parse_primary()

        while True:
            if self.check(TT.LPAREN):
                # 函数调用
                self.advance()
                args = []
                if not self.check(TT.RPAREN):
                    args.append(self.parse_expr())
                    while self.check(TT.COMMA):
                        self.advance()
                        args.append(self.parse_expr())
                self.expect(TT.RPAREN, "期望 ')'")
                expr = ast.Call(expr, args)
            elif self.check(TT.DOT):
                # 属性/方法访问
                self.advance()
                prop = self.expect(TT.IDENTIFIER, "期望属性名").value
                if self.check(TT.LPAREN):
                    # 方法调用
                    self.advance()
                    args = []
                    if not self.check(TT.RPAREN):
                        args.append(self.parse_expr())
                        while self.check(TT.COMMA):
                            self.advance()
                            args.append(self.parse_expr())
                    self.expect(TT.RPAREN, "期望 ')'")
                    expr = ast.MethodCall(expr, prop, args)
                else:
                    expr = ast.PropertyAccess(expr, prop)
            elif self.check(TT.LBRACKET):
                # 索引访问
                self.advance()
                index = self.parse_expr()
                self.expect(TT.RBRACKET, "期望 ']'")
                expr = ast.IndexAccess(expr, index)
            else:
                break

        return expr

    def parse_primary(self):
        tok = self.peek()

        # 数字
        if tok.type == TT.NUMBER:
            self.advance()
            return ast.NumberLit(tok.value)

        # 字符串
        if tok.type == TT.STRING:
            self.advance()
            return ast.StringLit(tok.value)

        # 布尔
        if tok.type == TT.TRUE:
            self.advance()
            return ast.BoolLit(True)
        if tok.type == TT.FALSE:
            self.advance()
            return ast.BoolLit(False)

        # 空
        if tok.type == TT.NULL:
            self.advance()
            return ast.NullLit()

        # 标识符（或单参数箭头函数）
        if tok.type == TT.IDENTIFIER:
            self.advance()
            # 单参数箭头函数: ident => expr
            if self.check(TT.ARROW):
                return self.parse_arrow_func_from_ident(tok)
            return ast.Identifier(tok.value)

        # 匿名函数
        if tok.type == TT.FUNC:
            return self.parse_anonymous_func()

        # 数组字面量
        if tok.type == TT.LBRACKET:
            return self.parse_array()

        # 对象字面量
        if tok.type == TT.LBRACE:
            return self.parse_object()

        # 括号表达式 or 多参数箭头函数: (x, y) => expr
        if tok.type == TT.LPAREN:
            self.advance()
            # 尝试解析为多参数箭头函数
            saved_pos = self.pos
            try:
                params = []
                if not self.check(TT.RPAREN):
                    if self.peek().type != TT.IDENTIFIER:
                        raise Exception("not arrow")
                    params.append(self.advance().value)
                    while self.check(TT.COMMA):
                        self.advance()
                        if self.peek().type != TT.IDENTIFIER:
                            raise Exception("not arrow")
                        params.append(self.advance().value)
                self.expect(TT.RPAREN)
                if self.check(TT.ARROW):
                    self.advance()  # consume =>
                    body_expr = self.parse_expr()
                    return ast.AnonymousFunc(params, [ast.ReturnStmt(body_expr)])
                # 不是箭头函数，回退
                self.pos = saved_pos
            except Exception:
                self.pos = saved_pos
            # 普通括号表达式
            expr = self.parse_expr()
            self.expect(TT.RPAREN, "期望 ')'")
            return expr

        self.error()

    def parse_anonymous_func(self):
        self.expect(TT.FUNC)
        self.expect(TT.LPAREN)
        params = self.parse_params()
        self.expect(TT.RPAREN)

        # 单行: 函数(参数) 返回 表达式 结束
        if self.check(TT.RETURN):
            self.advance()
            expr = self.parse_expr()
            self.expect(TT.END, "期望 '结束'")
            return ast.AnonymousFunc(params, [ast.ReturnStmt(expr)])

        # 多行: 函数(参数) ... 结束
        body = self.parse_block()
        self.expect(TT.END, "期望 '结束'")
        return ast.AnonymousFunc(params, body)

    def parse_array(self):
        self.expect(TT.LBRACKET)
        elements = []
        if not self.check(TT.RBRACKET):
            elements.append(self.parse_expr())
            while self.check(TT.COMMA):
                self.advance()
                if self.check(TT.RBRACKET):
                    break
                elements.append(self.parse_expr())
        self.expect(TT.RBRACKET, "期望 ']'")
        return ast.ArrayLit(elements)

    def parse_object(self):
        self.expect(TT.LBRACE)
        pairs = []
        if not self.check(TT.RBRACE):
            key = self.parse_expr()
            self.expect(TT.COLON, "期望 ':'")
            value = self.parse_expr()
            pairs.append((key, value))
            while self.check(TT.COMMA):
                self.advance()
                if self.check(TT.RBRACE):
                    break
                key = self.parse_expr()
                self.expect(TT.COLON, "期望 ':'")
                value = self.parse_expr()
                pairs.append((key, value))
        self.expect(TT.RBRACE, "期望 '}'")
        return ast.ObjectLit(pairs)

    def parse_class(self):
        self.advance() # "类"
        name = self.expect(TT.IDENTIFIER, "期望类名").value
        methods = []
        while not self.is_at_end() and not self.check(TT.END):
            if self.check(TT.FUNC):
                methods.append(self.parse_func_def())
            else:
                self.error("类定义中目前只支持函数")
        self.expect(TT.END, "期望 '结束'")
        return ast.ClassDef(name, methods)


def parse(tokens):
    """便捷函数"""
    return Parser(tokens).parse()
