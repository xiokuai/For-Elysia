import os

def patch():
    f = 'compiler/main.za'
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    # 1. Add TT constants
    content = content.replace(
        '常量 TT_DEFER = "DEFER"\n',
        '常量 TT_DEFER = "DEFER"\n常量 TT_ASYNC = "ASYNC"\n常量 TT_AWAIT = "AWAIT"\n常量 TT_MATCH = "MATCH"\n常量 TT_CASE = "CASE"\n常量 TT_QUESTION = "QUESTION"\n'
    )

    # 2. Add N constants
    content = content.replace(
        '常量 N_ANONYMOUS = "ANONYMOUS"\n',
        '常量 N_ANONYMOUS = "ANONYMOUS"\n常量 N_MATCH = "MATCH"\n常量 N_TRY_PROPAGATE = "TRY_PROPAGATE"\n常量 N_INTERPOLATED = "INTERPOLATED"\n'
    )

    # 3. Add to Lexer Keywords
    content = content.replace(
        '"延迟": TT_DEFER,\n',
        '"延迟": TT_DEFER, "异步": TT_ASYNC, "等待": TT_AWAIT, "匹配": TT_MATCH, "于": TT_CASE,\n'
    )

    # 4. Add to single char operators
    content = content.replace(
        '如果 字符 == "!" 则 词法前进(词法) 添加(词法单元, {"类型": TT_NOT_BANG, "值": "!", "行号": 行}) 继续 结束\n',
        '如果 字符 == "!" 则 词法前进(词法) 添加(词法单元, {"类型": TT_NOT_BANG, "值": "!", "行号": 行}) 继续 结束\n    如果 字符 == "?" 则 词法前进(词法) 添加(词法单元, {"类型": TT_QUESTION, "值": "?", "行号": 行}) 继续 结束\n'
    )

    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

patch()
