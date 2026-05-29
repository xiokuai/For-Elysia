import os

def patch():
    f = 'compiler/main.za'
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    compile_node_addition = """
  如果 类型 == N_TRY_PROPAGATE 则
    编译节点(生成器, 节点["表达式"])
    代码发射(生成器, "TRY_PROPAGATE", 空, 空, 空, 空, 空)
    返回
  结束

  如果 类型 == N_UNARY 则
"""
    content = content.replace('  如果 类型 == N_UNARY 则\n', compile_node_addition)

    # For N_MATCH, we add it to 编译语句
    compile_stmt_addition = """
  如果 类型 == N_MATCH 则
    // 转换 MATCH 为多个 IF-ELSE
    // let __target__ = target
    编译节点(生成器, 节点["目标"])
    代码发射变量定义(生成器, "__匹配目标__")
    代码发射(生成器, "POP", 空, 空, 空, 空, 空)

    让 分支数 = 长度(节点["分支"])
    让 结束跳转列表 = []
    让 索引值 = 0
    让 下一个假跳过 = 空

    当 索引值 < 分支数 时
      如果 下一个假跳过 != 空 则
        代码修补跳转(生成器, 下一个假跳过, 代码当前位置(生成器))
      结束

      让 分支 = 节点["分支"][索引值]
      // target == pattern
      代码发射变量读取(生成器, "__匹配目标__")
      编译节点(生成器, 分支["模式"])
      代码发射(生成器, "EQ", 空, 空, 空, 空, 空)
      
      下一个假跳过 = 代码发射(生成器, "JMP_IFNOT", 0, 空, 空, 空, 空)
      
      // 主体
      让 语句索引 = 0
      当 语句索引 < 长度(分支["主体"]) 时
        编译语句(生成器, 分支["主体"][语句索引])
        语句索引 = 语句索引 + 1
      结束
      
      添加(结束跳转列表, 代码发射(生成器, "JMP", 0, 空, 空, 空, 空))
      索引值 = 索引值 + 1
    结束

    如果 下一个假跳过 != 空 则
      代码修补跳转(生成器, 下一个假跳过, 代码当前位置(生成器))
    结束

    // 默认分支
    如果 节点["默认分支"] != 空 则
      让 语句索引 = 0
      当 语句索引 < 长度(节点["默认分支"]) 时
        编译语句(生成器, 节点["默认分支"][语句索引])
        语句索引 = 语句索引 + 1
      结束
    结束

    // 修补所有跳过
    索引值 = 0
    当 索引值 < 长度(结束跳转列表) 时
      代码修补跳转(生成器, 结束跳转列表[索引值], 代码当前位置(生成器))
      索引值 = 索引值 + 1
    结束

    返回
  结束

  如果 类型 == N_IF 则
"""
    content = content.replace('  如果 类型 == N_IF 则\n', compile_stmt_addition)

    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

patch()
