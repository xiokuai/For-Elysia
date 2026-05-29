import os

def patch():
    f = 'compiler/main.za'
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    # We need to replace the N_INTERPOLATED compilation block we added.
    old_block = """  如果 类型 == N_INTERPOLATED 则
    如果 长度(节点["片段"]) == 0 则
      代码发射(生成器, "PUSH", 代码添加常量(生成器, ""), 空, 空, 空, 空)
      返回
    结束

    编译节点(生成器, 节点["片段"][0])
    让 转换函数下标 = 代码添加常量(生成器, "转换文字")
    代码发射(生成器, "LOAD", 转换函数下标, 空, 空, 空, 空)
    代码发射(生成器, "SWAP", 空, 空, 空, 空, 空) // 将转换文字和第一个参数换位
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
  结束"""

    new_block = """  如果 类型 == N_INTERPOLATED 则
    如果 长度(节点["片段"]) == 0 则
      代码发射(生成器, "PUSH", 代码添加常量(生成器, ""), 空, 空, 空, 空)
      返回
    结束

    让 转换函数下标 = 代码添加常量(生成器, "转换文字")
    
    代码发射(生成器, "LOAD", 转换函数下标, 空, 空, 空, 空)
    编译节点(生成器, 节点["片段"][0])
    代码发射(生成器, "CALL", 1, 空, 空, 空, 空)
    
    让 索引值 = 1
    当 索引值 < 长度(节点["片段"]) 时
      代码发射(生成器, "LOAD", 转换函数下标, 空, 空, 空, 空)
      编译节点(生成器, 节点["片段"][索引值])
      代码发射(生成器, "CALL", 1, 空, 空, 空, 空)
      代码发射(生成器, "ADD", 空, 空, 空, 空, 空)
      索引值 = 索引值 + 1
    结束
    返回
  结束"""

    content = content.replace(old_block, new_block)

    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

patch()
