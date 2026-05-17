"""致爱编程语言 — CLI入口

用法:
    python -m zhiai                 # 启动REPL交互模式
    python -m zhiai 文件.za         # 执行致爱程序文件
    python -m zhiai 文件.zab        # 执行字节码文件
    python -m zhiai -e '代码'       # 执行单行代码
"""

import sys
import os

from .lexer import tokenize, LexError
from .parser import parse, ParseError
from .interpreter import Interpreter, Environment


def run_source(source, filename="<输入>", interpreter=None):
    """执行源代码"""
    if interpreter is None:
        interpreter = Interpreter()
    tokens = tokenize(source, filename)
    program = parse(tokens)
    interpreter.run(program)
    return interpreter


def run_file(filepath):
    """执行文件"""
    if not os.path.exists(filepath):
        print(f"错误: 文件不存在 '{filepath}'", file=sys.stderr)
        sys.exit(1)

    # .zab 字节码文件
    if filepath.endswith(".zab"):
        from .vm import VM
        vm = VM()
        vm.load_file(filepath)
        vm.run()
        return

    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        run_source(source, filepath)
    except LexError as e:
        print(f"词法错误: {e}", file=sys.stderr)
        sys.exit(1)
    except ParseError as e:
        print(f"语法错误: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"运行时错误: {e}", file=sys.stderr)
        sys.exit(1)


LOGO = r"""
$$$$$$$$\              $$$$$$$$\ $$\                     $$\           
\__$$  __|             $$  _____|$$ |                    \__|          
   $$ | $$$$$$\        $$ |      $$ |$$\   $$\  $$$$$$$\ $$\  $$$$$$\  
   $$ |$$  __$$\       $$$$$\    $$ |$$ |  $$ |$$  _____|$$ | \____$$\ 
   $$ |$$ /  $$ |      $$  __|   $$ |$$ |  $$ |\$$$$$$\  $$ | $$$$$$$ |
   $$ |$$ |  $$ |      $$ |      $$ |$$ |  $$ | \____$$\ $$ |$$  __$$ |
   $$ |\$$$$$$  |      $$$$$$$$\ $$ |\$$$$$$$ |$$$$$$$  |$$ |\$$$$$$$ |
   \__| \______/       \________|\__| \____$$ |\_______/ \__| \_______|
                                     $$\   $$ |                        
                                     \$$$$$$  |                        
                                      \______/                         
"""

def enable_ansi_escapes():
    import sys
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h_std_out = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(h_std_out, ctypes.byref(mode)):
                kernel32.SetConsoleMode(h_std_out, mode.value | 0x0004)
        except Exception:
            pass

def colorize_diagonal_gradient(text, start_rgb=(244, 114, 182), end_rgb=(168, 85, 247)):
    lines = text.splitlines()
    max_y = len(lines)
    max_x = max(len(line) for line in lines) if lines else 1
    
    colored_lines = []
    for y, line in enumerate(lines):
        colored_line = ""
        for x, char in enumerate(line):
            if char.isspace():
                colored_line += char
            else:
                ratio = (x / max_x + y / max_y) / 2.0
                r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
                g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
                b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
                colored_line += f"\033[38;2;{r};{g};{b}m{char}"
        colored_line += "\033[0m"
        colored_lines.append(colored_line)
    return "\n".join(colored_lines)

def repl():
    """交互式解释器"""
    enable_ansi_escapes()
    print(colorize_diagonal_gradient(LOGO.strip("\n")))
    print("╔══════════════════════════════════════╗")
    print("║    致爱 v1.0.7 — 中文编程语言       ║")
    print("║    输入 '退出' 或 Ctrl+C 结束        ║")
    print("╚══════════════════════════════════════╝")
    print()

    interpreter = Interpreter()

    while True:
        try:
            source = input("致爱 >>> ")
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not source.strip():
            continue
        if source.strip() in ("退出", "exit", "quit"):
            print("再见！")
            break

        # 检查是否是多行输入（以 结束 结尾的语句需要多行）
        if needs_more_lines(source):
            source = read_multiline(source)

        try:
            run_source(source, "<交互>", interpreter)
        except LexError as e:
            print(f"词法错误: {e}")
        except ParseError as e:
            print(f"语法错误: {e}")
        except RuntimeError as e:
            print(f"运行时错误: {e}")
        except Exception as e:
            print(f"错误: {e}")


def needs_more_lines(source):
    """检查是否需要更多行"""
    stripped = source.strip()
    multi_line_starts = ["如果", "当", "循环", "对于", "函数", "尝试"]
    for kw in multi_line_starts:
        if stripped.startswith(kw) and "结束" not in stripped:
            return True
    return False


def read_multiline(first_line):
    """读取多行输入"""
    lines = [first_line]
    while True:
        try:
            line = input("... ")
        except (EOFError, KeyboardInterrupt):
            break
        lines.append(line)
        if line.strip() == "结束":
            break
    return "\n".join(lines)


def main():
    """主入口"""
    args = sys.argv[1:]

    if not args:
        repl()
        return

    if args[0] == "-e":
        if len(args) < 2:
            print("用法: python -m zhiai -e '代码'", file=sys.stderr)
            sys.exit(1)
        try:
            run_source(args[1], "<命令行>")
        except (LexError, ParseError, RuntimeError) as e:
            print(f"错误: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if args[0] in ("-h", "--help"):
        print(__doc__)
        return

    if args[0] in ("-v", "--version"):
        from . import __version__, __lang_name__
        print(f"{__lang_name__} v{__version__}")
        return

    run_file(args[0])


if __name__ == "__main__":
    main()
