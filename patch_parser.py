import os

def patch():
    f = 'compiler/main.za'
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    # Add Match to parse_stmt
    content = content.replace(
        '  如果 当前类型 == TT_DEFER 则\n',
        '  如果 当前类型 == TT_MATCH 则 返回 解析匹配(解析器) 结束\n  如果 当前类型 == TT_DEFER 则\n'
    )

    # Add parse_match and parse_case_body functions
    parse_match_func = """
函数 解析匹配(解析器)
  语法期望(解析器, TT_MATCH, "期望 '匹配'")
  让 目标 = 解析表达式(解析器)
  语法期望(解析器, TT_CASE, "期望 '于'")
  让 分支列表 = []
  让 默认分支 = 空
  当 非 语法检查(解析器, TT_END) 并且 非 语法检查(解析器, TT_EOF) 时
    如果 语法检查(解析器, TT_ELSE) 则
      语法前进(解析器)
      如果 语法检查(解析器, TT_COLON) 则 语法前进(解析器) 结束
      默认分支 = 解析分支主体(解析器)
      中断
    结束
    让 模式 = 解析表达式(解析器)
    语法期望(解析器, TT_COLON, "期望 ':'")
    让 主体 = 解析分支主体(解析器)
    添加(分支列表, {"模式": 模式, "主体": 主体})
  结束
  语法期望(解析器, TT_END, "期望 '结束'")
  返回 {"类型": N_MATCH, "目标": 目标, "分支": 分支列表, "默认分支": 默认分支}
结束

函数 解析分支主体(解析器)
  让 语句 = []
  当 非 语法检查(解析器, TT_END) 并且 非 语法检查(解析器, TT_ELIF) 并且 非 语法检查(解析器, TT_ELSE) 并且 非 语法检查(解析器, TT_CATCH) 并且 非 语法检查(解析器, TT_EOF) 时
    如果 解析器["位置"] + 1 < 长度(解析器["词法单元"]) 并且 解析器["词法单元"][解析器["位置"] + 1]["类型"] == TT_COLON 则
      如果 语法检查(解析器, TT_ELSE) 则
        // 继续
      否则
        中断
      结束
    结束
    如果 语法检查(解析器, TT_ELSE) 则 中断 结束
    添加(语句, 解析语句(解析器))
  结束
  返回 语句
结束

函数 解析一元(解析器)
"""
    content = content.replace('函数 解析一元(解析器)\n', parse_match_func)

    # Modify parse_unary to parse ? (TryPropagate)
    content = content.replace(
        '  返回 解析调用链(解析器)\n结束\n\n函数 解析调用链(解析器)',
        '  让 表达式 = 解析调用链(解析器)\n  当 语法匹配(解析器, TT_QUESTION) 时\n    表达式 = {"类型": N_TRY_PROPAGATE, "表达式": 表达式}\n  结束\n  返回 表达式\n结束\n\n函数 解析调用链(解析器)'
    )

    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

patch()
