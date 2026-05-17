"""致爱编程语言 — 打包入口

用法:
    zhiai                         # 启动REPL交互模式
    zhiai run 文件.za [--jit]      # 解释执行或 JIT 执行致爱程序
    zhiai compile 文件.za         # 编译为字节码 .zab
    zhiai compile 文件.za --aot    # AOT 编译为高性能 EXE
    zhiai exec 文件.zab           # 执行字节码文件
    zhiai 文件.za [--jit]         # 编译并执行
    zhiai -e '代码'               # 执行单行代码
    zhiai -v                      # 版本信息
    zhiai install                 # 注册 .za/.zab 文件关联
    zhiai uninstall               # 移除文件关联
"""

import sys
import os
import ctypes

def get_base_path():
    """获取资源文件基础路径（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def setup_zhiai_path():
    """确保 zhiai 模块可以被导入"""
    base = get_base_path()
    if base not in sys.path:
        sys.path.insert(0, base)

def get_compiler_path():
    """获取编译器源码路径"""
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    base = get_base_path()
    
    paths = [
        os.path.join(exe_dir, "compiler", "main.za"),
        os.path.join(base, "compiler", "main.za"),
        os.path.join(os.getcwd(), "compiler", "main.za")
    ]
    for p in paths:
        if os.path.exists(p): return p
        
    print("错误: 找不到编译器源码 compiler/main.za", file=sys.stderr)
    sys.exit(1)

def cmd_repl():
    setup_zhiai_path()
    from zhiai.__main__ import repl
    repl()

def cmd_run_za(filepath, jit=False):
    setup_zhiai_path()
    if jit:
        from zhiai.lexer import tokenize
        from zhiai.parser import parse
        from zhiai.jit import exec_jit
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        tokens = tokenize(source, filepath)
        program = parse(tokens)
        exec_jit(program)
    else:
        from zhiai.__main__ import run_file
        run_file(filepath)

def cmd_run_zab(filepath, fast=False):
    setup_zhiai_path()
    try:
        from zhiai._fastvm import VM
    except ImportError:
        from zhiai.vm import VM
    vm = VM()
    vm.load_file(filepath)
    vm.run()

def cmd_compile(input_file, output_file=None):
    if output_file is None:
        output_file = os.path.splitext(input_file)[0] + ".zab"
    setup_zhiai_path()
    compiler_path = get_compiler_path()
    from zhiai.lexer import tokenize
    from zhiai.parser import parse
    from zhiai.interpreter import Interpreter
    with open(compiler_path, "r", encoding="utf-8") as f:
        compiler_source = f.read()
    old_argv = sys.argv[:]
    sys.argv = ["zhiai", "compile", input_file, "-o", output_file]
    try:
        tokens = tokenize(compiler_source, compiler_path)
        program = parse(tokens)
        Interpreter().run(program)
    finally:
        sys.argv = old_argv

def cmd_compile_aot(input_file, output_exe=None):
    """用 Nuitka 将 .za 编译为 AOT 原生 EXE"""
    setup_zhiai_path()
    from zhiai.lexer import tokenize
    from zhiai.parser import parse
    from zhiai.jit import JITCompiler
    if output_exe is None:
        output_exe = os.path.splitext(input_file)[0] + ".exe"
    print(f"[信息] 正在转译 {input_file} 为 Python...")
    with open(input_file, "r", encoding="utf-8") as f:
        source = f.read()
    tokens = tokenize(source, input_file)
    program = parse(tokens)
    py_source = JITCompiler().compile(program)
    temp_py = "temp_aot_target.py"
    with open(temp_py, "w", encoding="utf-8") as f:
        f.write("# -*- coding: utf-8 -*-\nimport sys, os\n")
        f.write("from zhiai.builtins import BUILTINS\n")
        f.write("from zhiai.jit import _za_get_prop, _za_set_prop, _za_method_call\n\n")
        f.write(py_source)
    print(f"[信息] 正在调用 Nuitka 进行 AOT 编译...")
    import subprocess
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "nuitka"], capture_output=True)
        cmd = [sys.executable, "-m", "nuitka", "--onefile", "--standalone", 
               "--output-filename=" + os.path.basename(output_exe),
               "--output-dir=" + os.path.dirname(os.path.abspath(output_exe)), temp_py]
        subprocess.run(cmd, check=True)
        print(f"[成功] AOT 编译完成: {output_exe}")
    except Exception as e:
        print(f"[错误] AOT 编译失败: {e}", file=sys.stderr)
    finally:
        if os.path.exists(temp_py): os.remove(temp_py)

def cmd_compile_and_run(input_file, fast=False, jit=False):
    if jit:
        cmd_run_za(input_file, jit=True)
    else:
        zab_file = os.path.splitext(input_file)[0] + ".zab"
        cmd_compile(input_file, zab_file)
        cmd_run_zab(zab_file, fast=fast)

def cmd_eval(code):
    setup_zhiai_path()
    from zhiai.lexer import tokenize
    from zhiai.parser import parse
    from zhiai.interpreter import Interpreter
    tokens = tokenize(code, "<eval>")
    program = parse(tokens)
    Interpreter().run(program)

def cmd_install():
    # 注册文件关联 (Windows 专用)
    if sys.platform != "win32": return
    import winreg
    exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
    for ext in [".za", ".zab"]:
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, ext)
        winreg.SetValue(key, "", winreg.REG_SZ, "ZhiaiFile")
        winreg.CloseKey(key)
    key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, "ZhiaiFile\\shell\\open\\command")
    winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')
    winreg.CloseKey(key)
    print("已成功注册文件关联 (.za, .zab)")

def cmd_uninstall():
    if sys.platform != "win32": return
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, ".za")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, ".zab")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, "ZhiaiFile\\shell\\open\\command")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, "ZhiaiFile\\shell\\open")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, "ZhiaiFile\\shell")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, "ZhiaiFile")
        print("已移除文件关联")
    except: pass

def pause():
    if sys.stdin.isatty():
        try: input("\n按 Enter 键继续...")
        except: pass

def main():
    args = sys.argv[1:]
    if not args: cmd_repl(); return
    
    fast = "--fast" in args
    jit = "--jit" in args
    aot = "--aot" in args
    args = [a for a in args if a not in ("--fast", "--jit", "--aot")]
    if not args: return
    
    cmd = args[0]
    if cmd == "run":
        if len(args) < 2: sys.exit(1)
        if args[1].endswith(".zab"): cmd_run_zab(args[1], fast)
        else: cmd_run_za(args[1], jit)
    elif cmd == "compile":
        if len(args) < 2: sys.exit(1)
        out = None
        if "-o" in args:
            idx = args.index("-o")
            if idx + 1 < len(args): out = args[idx+1]
        if aot: cmd_compile_aot(args[1], out)
        else: cmd_compile(args[1], out)
    elif cmd == "exec":
        if len(args) < 2: sys.exit(1)
        cmd_run_zab(args[1], fast)
    elif cmd == "-e":
        if len(args) < 2: sys.exit(1)
        cmd_eval(args[1])
    elif cmd == "install": cmd_install()
    elif cmd == "uninstall": cmd_uninstall()
    elif cmd in ("-v", "--version"): print("致爱 v1.0.10 (Ultimate High-Performance Edition)")
    elif cmd in ("-h", "--help"): print(__doc__)
    else:
        if os.path.exists(cmd):
            if cmd.endswith(".zab"): cmd_run_zab(cmd, fast)
            else: cmd_compile_and_run(cmd, fast, jit)
        else: print(f"未知命令或文件: {cmd}")
    pause()

if __name__ == "__main__":
    main()
