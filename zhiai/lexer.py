"""致爱词法分析器 — 将源代码转换为token流"""

from dataclasses import dataclass
from enum import Enum, auto


class TT(Enum):
    """Token类型"""
    # 字面量
    NUMBER = auto()
    STRING = auto()

    # 标识符 & 关键字
    IDENTIFIER = auto()
    LET = auto()          # 让
    CONST = auto()        # 常量
    IF = auto()           # 如果
    ELIF = auto()         # 否则如果
    ELSE = auto()         # 否则
    WHILE = auto()        # 当
    FOR = auto()          # 循环
    FROM = auto()         # 从
    TO = auto()           # 到
    STEP = auto()         # 步长
    EACH = auto()         # 每个
    IN = auto()           # 在
    MID = auto()          # 中
    FUNC = auto()         # 函数
    RETURN = auto()       # 返回
    BREAK = auto()        # 中断
    CONTINUE = auto()     # 继续
    TRUE = auto()         # 真
    FALSE = auto()        # 假
    NULL = auto()         # 空
    AND = auto()          # 并且
    OR = auto()           # 或者
    NOT = auto()          # 非
    TRY = auto()          # 尝试
    CATCH = auto()        # 捕获
    END = auto()          # 结束
    DEFER = auto()        # 延迟


    # 运算符
    PLUS = auto()         # +
    MINUS = auto()        # -
    STAR = auto()         # *
    SLASH = auto()        # /
    PERCENT = auto()      # %
    POWER = auto()        # **
    EQ = auto()           # =
    EQEQ = auto()         # ==
    NEQ = auto()          # !=
    LT = auto()           # <
    GT = auto()           # >
    LTE = auto()          # <=
    GTE = auto()          # >=
    NOT_BANG = auto()     # ! (非的简写)
    AND_AND = auto()      # && (并且的简写)
    OR_OR = auto()        # || (或者的简写)

    # 分隔符
    LPAREN = auto()       # (
    RPAREN = auto()       # )
    LBRACKET = auto()     # [
    RBRACKET = auto()     # ]
    LBRACE = auto()       # {
    RBRACE = auto()       # }
    COMMA = auto()        # ,
    COLON = auto()        # :
    DOT = auto()          # .
    PLUS_EQ = auto()      # +=
    MINUS_EQ = auto()     # -=
    STAR_EQ = auto()      # *=
    SLASH_EQ = auto()     # /=
    ARROW = auto()        # => 箭头函数
    EOF = auto()


KEYWORDS = {
    "让": TT.LET,
    "常量": TT.CONST,
    "如果": TT.IF,
    "否则如果": TT.ELIF,
    "否则": TT.ELSE,
    "当": TT.WHILE,
    "循环": TT.FOR,
    "对于": TT.FOR,
    "从": TT.FROM,
    "到": TT.TO,
    "步长": TT.STEP,
    "每个": TT.EACH,
    "在": TT.IN,
    "中": TT.MID,
    "函数": TT.FUNC,
    "返回": TT.RETURN,
    "中断": TT.BREAK,
    "继续": TT.CONTINUE,
    "真": TT.TRUE,
    "假": TT.FALSE,
    "空": TT.NULL,
    "并且": TT.AND,
    "或者": TT.OR,
    "非": TT.NOT,
    "尝试": TT.TRY,
    "捕获": TT.CATCH,
    "结束": TT.END,
    "延迟": TT.DEFER,
}


@dataclass
class Token:
    type: TT
    value: object
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, 行{self.line})"


class LexError(Exception):
    def __init__(self, message, line, col):
        super().__init__(f"词法错误 行{line}列{col}: {message}")
        self.line = line
        self.col = col


class Lexer:
    """词法分析器"""

    def __init__(self, source, filename="<输入>"):
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []

    def error(self, message):
        raise LexError(message, self.line, self.col)

    def peek(self):
        if self.pos < len(self.source):
            return self.source[self.pos]
        return None

    def advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def match(self, expected):
        if self.pos < len(self.source) and self.source[self.pos] == expected:
            return self.advance()
        return None

    def skip_whitespace_and_comments(self):
        while self.pos < len(self.source):
            ch = self.peek()
            # 空白
            if ch in " \t\r\n":
                self.advance()
            # 单行注释 //
            elif ch == "/" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "/":
                while self.pos < len(self.source) and self.peek() != "\n":
                    self.advance()
            # 多行注释 /* ... */
            elif ch == "/" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "*":
                start_line, start_col = self.line, self.col
                self.advance()  # /
                self.advance()  # *
                while self.pos < len(self.source):
                    if self.peek() == "*" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "/":
                        self.advance()  # *
                        self.advance()  # /
                        break
                    self.advance()
                else:
                    raise LexError("未闭合的多行注释", start_line, start_col)
            else:
                break

    def is_chinese(self, ch):
        """判断是否为中文字符"""
        cp = ord(ch)
        return (0x4E00 <= cp <= 0x9FFF or   # CJK统一汉字
                0x3400 <= cp <= 0x4DBF or   # CJK扩展A
                0xF900 <= cp <= 0xFAFF or   # CJK兼容
                0x20000 <= cp <= 0x2A6DF)   # CJK扩展B

    def is_ident_start(self, ch):
        return ch.isalpha() or ch == "_" or self.is_chinese(ch)

    def is_ident_char(self, ch):
        return ch.isalnum() or ch == "_" or self.is_chinese(ch)

    def read_string(self, quote):
        """读取字符串"""
        start_line, start_col = self.line, self.col
        self.advance()  # 跳过开始引号
        parts = []
        current = []

        while self.pos < len(self.source):
            ch = self.peek()
            if ch == "\\":
                self.advance()
                esc = self.advance() if self.pos < len(self.source) else None
                escape_map = {"n": "\n", "t": "\t", "\\": "\\", "'": "'", '"': '"'}
                if esc in escape_map:
                    current.append(escape_map[esc])
                elif esc is None:
                    self.error("字符串未结束")
                else:
                    current.append("\\" + esc)
            elif ch == quote:
                self.advance()
                parts.append("".join(current))
                return "".join(parts)
            elif ch == "\n":
                current.append(self.advance())
            else:
                current.append(self.advance())

        raise LexError("字符串未结束", start_line, start_col)

    def read_number(self):
        """读取数字"""
        start = self.pos
        has_dot = False

        while self.pos < len(self.source):
            ch = self.peek()
            if ch.isdigit():
                self.advance()
            elif ch == "." and not has_dot:
                # 检查下一个字符是否是数字，避免将 . 当作小数点
                if self.pos + 1 < len(self.source) and self.source[self.pos + 1].isdigit():
                    has_dot = True
                    self.advance()
                else:
                    break
            else:
                break

        text = self.source[start:self.pos]
        if has_dot:
            return float(text)
        return int(text)

    def read_identifier(self):
        """读取标识符或关键字"""
        start = self.pos
        while self.pos < len(self.source) and self.is_ident_char(self.peek()):
            self.advance()
        return self.source[start:self.pos]

    def tokenize(self):
        """将源代码转换为token列表"""
        while self.pos < len(self.source):
            self.skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break

            ch = self.peek()
            start_line, start_col = self.line, self.col

            # 字符串
            if ch in ('"', "'"):
                value = self.read_string(ch)
                self.tokens.append(Token(TT.STRING, value, start_line, start_col))
                continue

            # 数字
            if ch.isdigit():
                value = self.read_number()
                self.tokens.append(Token(TT.NUMBER, value, start_line, start_col))
                continue

            # 标识符 / 关键字
            if self.is_ident_start(ch):
                text = self.read_identifier()
                tt = KEYWORDS.get(text, TT.IDENTIFIER)
                if tt == TT.TRUE:
                    self.tokens.append(Token(TT.TRUE, True, start_line, start_col))
                elif tt == TT.FALSE:
                    self.tokens.append(Token(TT.FALSE, False, start_line, start_col))
                elif tt == TT.NULL:
                    self.tokens.append(Token(TT.NULL, None, start_line, start_col))
                else:
                    self.tokens.append(Token(tt, text, start_line, start_col))
                continue

            # 双字符运算符
            if ch == "=" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.EQEQ, "==", start_line, start_col))
                continue
            if ch == "!" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.NEQ, "!=", start_line, start_col))
                continue
            if ch == "<" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.LTE, "<=", start_line, start_col))
                continue
            if ch == ">" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.GTE, ">=", start_line, start_col))
                continue
            # => 箭头函数
            if ch == "=" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == ">":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.ARROW, "=>", start_line, start_col))
                continue
            if ch == "*" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "*":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.POWER, "**", start_line, start_col))
                continue
            if ch == "&" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "&":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.AND_AND, "&&", start_line, start_col))
                continue
            if ch == "|" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "|":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.OR_OR, "||", start_line, start_col))
                continue
            if ch == "+" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.PLUS_EQ, "+=", start_line, start_col))
                continue
            if ch == "-" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.MINUS_EQ, "-=", start_line, start_col))
                continue
            if ch == "*" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.STAR_EQ, "*=", start_line, start_col))
                continue
            if ch == "/" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
                self.advance(); self.advance()
                self.tokens.append(Token(TT.SLASH_EQ, "/=", start_line, start_col))
                continue

            # 单字符运算符
            single = {
                "+": TT.PLUS, "-": TT.MINUS, "*": TT.STAR, "/": TT.SLASH,
                "%": TT.PERCENT, "=": TT.EQ, "<": TT.LT, ">": TT.GT,
                "!": TT.NOT_BANG,
                "(": TT.LPAREN, ")": TT.RPAREN,
                "[": TT.LBRACKET, "]": TT.RBRACKET,
                "{": TT.LBRACE, "}": TT.RBRACE,
                ",": TT.COMMA, ":": TT.COLON, ".": TT.DOT,
            }
            if ch in single:
                self.advance()
                self.tokens.append(Token(single[ch], ch, start_line, start_col))
                continue

            self.error(f"未知字符 '{ch}'")

        self.tokens.append(Token(TT.EOF, None, self.line, self.col))
        return self.tokens


def tokenize(source, filename="<输入>"):
    """便捷函数"""
    return Lexer(source, filename).tokenize()
