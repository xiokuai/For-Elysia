import sys
import os

def format_code(code):
    # 1. 运行词法分析器获取真实 Token 流
    from zhiai.lexer import tokenize, TT
    try:
        tokens = tokenize(code)
    except Exception:
        # 如果代码当前有语法错无法词法分析，则降级回原样，避免破坏用户输入
        return code

    # 2. 按行对真实 Token 进行分组
    line_tokens = {}
    for tok in tokens:
        if tok.type == TT.EOF:
            continue
        line_tokens.setdefault(tok.line, []).append(tok)

    # 3. 逐行重新排版
    lines = code.split('\n')
    formatted = []
    indent_level = 0
    indent_str = "    " # 使用 4 空格作为标准缩进

    for i, line_content in enumerate(lines):
        line_num = i + 1
        trimmed = line_content.strip()
        
        if not trimmed:
            formatted.append("")
            continue

        # 从该行的真实 Token 中提取关键字
        toks = line_tokens.get(line_num, [])
        types = [t.type for t in toks]
        
        # 判断是否是真正的块关闭/中转词
        has_end = TT.END in types
        has_else_or_elif = (TT.ELSE in types) or (TT.ELIF in types)
        has_catch = TT.CATCH in types

        # 判断是否是真正的块开启词
        has_if = TT.IF in types
        has_while = TT.WHILE in types
        has_for = TT.FOR in types
        has_func = TT.FUNC in types
        has_try = TT.TRY in types
        # 兼容 class/类 的块开启（由于类不是保留关键字而是标识符，可以通过名称判断）
        has_class = any(t.type == TT.IDENTIFIER and t.value == "类" for t in toks)

        # 块开启判断
        is_block_start = has_if or has_while or has_for or has_func or has_try or has_class

        # 如果是“结束”，在打印该行前减少缩进
        if has_end:
            indent_level = max(0, indent_level - 1)

        # 如果是“否则/否则如果/捕获”，临时减少缩进打印该行，但不改变基础缩进
        current_indent = indent_level
        if (has_else_or_elif or has_catch) and not has_end:
            current_indent = max(0, indent_level - 1)

        # 输出带缩进的行
        formatted.append((indent_str * current_indent) + trimmed)

        # 在这行打印完后，如果是开启新块，则增加下一行的缩进
        # 如果该行同时有“结束”（例如单行表达式 `如果 真 则 返回 结束`），则不应增加缩进
        if is_block_start and not has_end:
            # “否则”和“捕获”本身就是块的中转，不应该重复叠加缩进
            indent_level += 1
            
    return '\n'.join(formatted)

def main():
    if len(sys.argv) < 2:
        print("致爱代码格式化工具 v1.6.0")
        print("用法: python zhiai_fmt.py <文件.za>")
        return
        
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"文件不存在: {path}")
        return
        
    # 确保 zhiai 模块可以导入
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    formatted = format_code(content)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(formatted)
    print(f"已格式化: {path}")

if __name__ == "__main__":
    main()
