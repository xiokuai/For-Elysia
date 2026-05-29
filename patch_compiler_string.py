import os

def patch():
    f = 'compiler/main.za'
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    compile_node_addition = """
  如果 类型 == N_INTERPOLATED 则
    如果 长度(节点["片段"]) == 0 则
      代码发射(生成器, "PUSH", 代码添加常量(生成器, ""), 空, 空, 空, 空)
      返回
    结束

    编译节点(生成器, 节点["片段"][0])
    让 转换函数下标 = 代码添加常量(生成器, "转换文字")
    代码发射(生成器, "LOAD", 转换函数下标, 空, 空, 空, 空)
    代码发射(生成器, "SWAP", 空, 空, 空, 空, 空) # 将转换文字和第一个参数换位
    代码发射(生成器, "CALL", 1, 空, 空, 空, 空)
    
    让 索引值 = 1
    当 索引值 < 长度(节点["片段"]) 时
      编译节点(生成器, 节点["片段"][索引值])
      代码发射(生成器, "LOAD", 转换函数下标, 空, 空, 空, 空)
      代码发射(生成器, "SWAP", 空, 空, 空, 空, 空)
      代码发射(生成器, "CALL", 1, 空, 空, 空, 空)
      代码发射(生成器, "ADD", 空, 空, 空, 空, 空)
      索引值 = 索引值 + 1
    结束
    返回
  结束

  如果 类型 == N_ANONYMOUS 则
"""
    content = content.replace('  如果 类型 == N_ANONYMOUS 则\n', compile_node_addition)

    # Wait, the parser doesn't generate N_INTERPOLATED. Let me add parse_interpolated_string in compiler parser!
    
    # Wait, the string tokenizer in compiler/main.za does not support '{}' substitution.
    # It just returns TT_STRING.
    # We need to change how compiler tokenizes TT_STRING, or change parser to handle `{}` in TT_STRING.
    # But writing regex in Zhiai without regex engine is hard. 
    # Let me add a simple interpolation parser in the compiler parser.

    parse_string_addition = """
  // 字符串
  如果 当前["类型"] == TT_STRING 则
    语法前进(解析器)
    让 文本 = 当前["值"]
    // 简易插值检查 (暂时只支持简单的单变量插值，如 "你好 {名字}")
    让 有括号 = 假
    让 索引值 = 0
    当 索引值 < 长度(文本) 时
      如果 文本[索引值] == "{" 则 有括号 = 真 中断 结束
      索引值 = 索引值 + 1
    结束
    
    如果 有括号 则
      让 片段 = []
      让 文本缓冲 = ""
      让 处于表达式 = 假
      让 表达式缓冲 = ""
      索引值 = 0
      当 索引值 < 长度(文本) 时
        让 字符 = 文本[索引值]
        如果 处于表达式 则
          如果 字符 == "}" 则
            处于表达式 = 假
            // 简单处理: 假定括号内是一个标识符
            添加(片段, {"类型": N_IDENT, "名称": 表达式缓冲})
            表达式缓冲 = ""
          否则
            表达式缓冲 = 表达式缓冲 + 字符
          结束
        否则
          如果 字符 == "{" 则
            如果 文本缓冲 != "" 则
              添加(片段, {"类型": N_STRING, "值": 文本缓冲})
              文本缓冲 = ""
            结束
            处于表达式 = 真
          否则
            文本缓冲 = 文本缓冲 + 字符
          结束
        结束
        索引值 = 索引值 + 1
      结束
      如果 文本缓冲 != "" 则
        添加(片段, {"类型": N_STRING, "值": 文本缓冲})
      结束
      返回 {"类型": N_INTERPOLATED, "片段": 片段}
    结束

    返回 {"类型": N_STRING, "值": 文本}
  结束

  // 布尔
"""
    content = content.replace('  // 字符串\n  如果 当前["类型"] == TT_STRING 则\n    语法前进(解析器)\n    返回 {"类型": N_STRING, "值": 当前["值"]}\n  结束\n\n  // 布尔\n', parse_string_addition)

    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

patch()
