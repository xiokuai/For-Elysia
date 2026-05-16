"""致爱编程语言 — 打包入口

用法:
    zhiai                         # 启动REPL交互模式
    zhiai run 文件.za [--jit]      # 解释执行或 JIT 执行致爱程序
    zhiai compile 文件.za         # 编译为字节码 .zab
    zhiai compile 文件.za -o x.zab
    zhiai exec 文件.zab           # 执行字节码文件
    zhiai 文件.za [--jit]         # 编译并执行
    zhiai 文件.zab                # 执行字节码
    zhiai -e '代码'               # 执行单行代码
    zhiai -v                      # 版本信息
    zhiai install                 # 注册 .za/.zab 文件关联
    zhiai uninstall               # 移除文件关联
    zhiai zap install <名> <URL>   # 安装模块包
    zhiai fmt <文件.za>           # 格式化代码
    zhiai debug <文件.zab>        # 调试运行
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
    # 优先查找 exe 所在目录（用户可能把 compiler 文件夹放在旁边）
    exe_dir = os.path.dirname(get_exe_path())
    compiler_main = os.path.join(exe_dir, "compiler", "main.za")
    if os.path.exists(compiler_main):
        return compiler_main

    # 其次查找打包时的临时目录（PyInstaller --add-data 打包进去的）
    base = get_base_path()
    compiler_main = os.path.join(base, "compiler", "main.za")
    if os.path.exists(compiler_main):
        return compiler_main

    print("错误: 找不到编译器源码 compiler/main.za", file=sys.stderr)
    print(f"  查找路径:", file=sys.stderr)
    print(f"    {os.path.join(exe_dir, 'compiler', 'main.za')}", file=sys.stderr)
    print(f"    {os.path.join(base, 'compiler', 'main.za')}", file=sys.stderr)
    sys.exit(1)


def cmd_repl():
    """启动 REPL"""
    setup_zhiai_path()
    from zhiai.__main__ import repl
    repl()


def cmd_run_za(filepath, jit=False):
    """执行 .za 文件"""
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
    """VM 执行 .zab 文件"""
    setup_zhiai_path()
    if fast:
        try:
            from zhiai._fastvm import VM
            print("[信息] 使用高速 VM 模式")
        except ImportError:
            from zhiai.vm import VM
            print("[警告] 找不到高速 VM 模块，回退到标准模式")
    else:
        from zhiai.vm import VM
        
    vm = VM()
    vm.load_file(filepath)
    vm.run()


def cmd_compile(input_file, output_file=None):
    """用自举编译器编译 .za → .zab"""
    if not os.path.exists(input_file):
        print(f"错误: 文件不存在 '{input_file}'", file=sys.stderr)
        sys.exit(1)

    if output_file is None:
        base_name = os.path.splitext(input_file)[0]
        output_file = base_name + ".zab"

    setup_zhiai_path()
    compiler_path = get_compiler_path()

    # 用解释器运行编译器，传入输入和输出路径
    from zhiai.lexer import tokenize
    from zhiai.parser import parse
    from zhiai.interpreter import Interpreter

    with open(compiler_path, "r", encoding="utf-8") as f:
        compiler_source = f.read()

    # 通过 sys.argv 传递参数给编译器
    # 命令行参数() 返回 sys.argv[2:]，所以前两个是占位符
    old_argv = sys.argv[:]
    sys.argv = ["python", "compiler/main.za", input_file, "-o", output_file]

    try:
        tokens = tokenize(compiler_source, compiler_path)
        program = parse(tokens)
        interpreter = Interpreter()
        interpreter.run(program)
    except SystemExit:
        pass
    except Exception as e:
        print(f"编译错误: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        sys.argv = old_argv


def cmd_compile_and_run(input_file, fast=False, jit=False):
    """编译并执行"""
    if jit:
        cmd_run_za(input_file, jit=True)
        return
    base_name = os.path.splitext(input_file)[0]
    zab_file = base_name + ".zab"
    cmd_compile(input_file, zab_file)
    print()
    cmd_run_zab(zab_file, fast=fast)


def cmd_compile_exe(input_file, output_file=None):
    """编译为独立的可执行文件 (.exe)"""
    import subprocess
    import shutil
    
    # 1. 先编译为 .zab
    base_name = os.path.splitext(input_file)[0]
    zab_file = base_name + ".zab"
    if output_file is None:
        exe_name = base_name
    else:
        exe_name = os.path.splitext(output_file)[0]
        
    cmd_compile(input_file, zab_file)
    print("生成字节码成功，开始打包为 EXE...")
    
    # 2. 读取生成的 .zab 并将其嵌入到启动脚本中，避免复杂的数据文件打包
    with open(zab_file, "r", encoding="utf-8") as f:
        bytecode = f.read()
        
    boot_script = f"""# 自动生成的启动引导程序
import sys
import os

# 将致爱虚拟机和运行环境导入
from zhiai.vm import VM

def main():
    bytecode_str = {repr(bytecode)}
    vm = VM()
    vm.load(bytecode_str)
    try:
        vm.run()
    except Exception as e:
        print(f"运行时错误: {{e}}")
        if not sys.stdin.isatty():
            input("按 Enter 退出...")

if __name__ == "__main__":
    main()
"""
    boot_file = "_boot.py"
    with open(boot_file, "w", encoding="utf-8") as f:
        f.write(boot_script)
        
    # 3. 使用 PyInstaller 打包
    pyinstaller_cmd = [
        "pyinstaller", "--onefile", boot_file,
        "--name", exe_name,
        "--noconfirm"
    ]
    
    # 如果根目录有 logo.ico，加上图标
    logo_path = os.path.join(get_base_path(), "logo.ico")
    if os.path.exists(logo_path):
        pyinstaller_cmd.extend(["--icon", logo_path])
        
    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print(f"打包成功！可执行文件位于 dist/{exe_name}.exe")
        
        # 将生成的 EXE 移动到当前目录
        exe_path = os.path.join("dist", exe_name + ".exe")
        if os.path.exists(exe_path):
            target_path = exe_name + ".exe"
            shutil.copy(exe_path, target_path)
            print(f"已移动到当前目录: {target_path}")
            
    except subprocess.CalledProcessError:
        print("打包 EXE 失败，请确保已安装 PyInstaller (pip install pyinstaller)", file=sys.stderr)
    finally:
        # 4. 清理临时文件
        if os.path.exists(boot_file):
            os.remove(boot_file)
        if os.path.exists(zab_file):
            os.remove(zab_file)  # 对于 EXE 我们不需要留着 zab


def cmd_eval(code):
    """执行单行代码"""
    setup_zhiai_path()
    from zhiai.__main__ import run_source
    from zhiai.lexer import LexError
    from zhiai.parser import ParseError
    try:
        run_source(code, "<命令行>")
    except (LexError, ParseError, RuntimeError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def get_exe_path():
    """获取 zhiai.exe 的真实路径"""
    if getattr(sys, 'frozen', False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(__file__)


def cmd_install():
    """注册 .za 和 .zab 文件关联 + 添加 PATH"""
    if os.name != "nt":
        print("错误: 文件关联仅支持 Windows", file=sys.stderr)
        sys.exit(1)

    import winreg
    exe_path = get_exe_path()
    exe_dir = os.path.dirname(exe_path)

    # 用 HKEY_CURRENT_USER，不需要管理员权限
    print("正在注册文件关联...")
    print()

    def set_assoc(ext, prog_id, desc, verb, cmd_template):
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, prog_id)
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, desc)
        winreg.CloseKey(key)

        icon_key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, prog_id + "\\DefaultIcon"
        )
        winreg.SetValueEx(icon_key, None, 0, winreg.REG_SZ, f"{exe_path},0")
        winreg.CloseKey(icon_key)

        cmd_key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            prog_id + f"\\shell\\{verb}\\command"
        )
        winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, cmd_template)
        winreg.CloseKey(cmd_key)

        ext_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, ext)
        winreg.SetValueEx(ext_key, None, 0, winreg.REG_SZ, prog_id)
        winreg.CloseKey(ext_key)

        # OpenWithProgids 确保 Windows 识别文件关联
        owp_key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts"
            + ext + r"\OpenWithProgids"
        )
        winreg.SetValueEx(owp_key, prog_id, 0, winreg.REG_NONE, b"")
        winreg.CloseKey(owp_key)

    set_assoc(
        ".za", "ZhIAi.Source", "致爱源码文件", "open",
        f'"{exe_path}" "%1" %*'
    )
    print("  .za  -> 编译并运行")

    set_assoc(
        ".zab", "ZhIAi.Bytecode", "致爱字节码文件", "open",
        f'"{exe_path}" exec "%1" %*'
    )
    print("  .zab -> 直接运行")

    # 添加到用户 PATH（不需要管理员权限）
    env_key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Environment",
        0, winreg.KEY_ALL_ACCESS
    )
    try:
        current_path, _ = winreg.QueryValueEx(env_key, "Path")
    except FileNotFoundError:
        current_path = ""
    winreg.CloseKey(env_key)

    if isinstance(current_path, list):
        current_path = ";".join(str(x) for x in current_path)

    if exe_dir not in current_path:
        new_path = (current_path.rstrip(";") + ";" + exe_dir).lstrip(";")
        env_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0, winreg.KEY_ALL_ACCESS
        )
        winreg.SetValueEx(env_key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(env_key)
        print("  PATH   -> 已添加到用户环境变量")
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, 0)
    else:
        print("  PATH   -> 已存在，跳过")

    # 刷新图标缓存
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass

    print()
    print("注册完成！")
    print("  - 双击 .za / .zab 文件可直接运行")
    print("  - 新开命令行窗口即可直接使用 zhiai 命令")


def cmd_uninstall():
    """移除 .za 和 .zab 文件关联"""
    if os.name != "nt":
        print("错误: 文件关联仅支持 Windows", file=sys.stderr)
        sys.exit(1)

    import winreg

    def delete_tree(root, subkey):
        try:
            key = winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS)
            while True:
                try:
                    child = winreg.EnumKey(key, 0)
                    delete_tree(root, f"{subkey}\\{child}")
                except OSError:
                    break
            winreg.CloseKey(key)
            winreg.DeleteKey(root, subkey)
        except OSError:
            pass

    print("正在移除文件关联...")

    for ext in [".za", ".zab"]:
        for root in [winreg.HKEY_CURRENT_USER, winreg.HKEY_CLASSES_ROOT]:
            try:
                key = winreg.OpenKey(root, ext, 0, winreg.KEY_READ)
                prog_id, _ = winreg.QueryValueEx(key, None)
                winreg.CloseKey(key)
                delete_tree(root, prog_id)
            except OSError:
                pass
            try:
                winreg.DeleteKey(root, ext)
            except OSError:
                pass
        print(f"  {ext} 已移除")

    # 从用户 PATH 中移除
    exe_path = get_exe_path()
    exe_dir = os.path.dirname(exe_path)
    try:
        env_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Environment",
            0, winreg.KEY_ALL_ACCESS
        )
        current_path, _ = winreg.QueryValueEx(env_key, "Path")
        if isinstance(current_path, list):
            current_path = ";".join(str(x) for x in current_path)
        parts = [p for p in current_path.split(";") if p and p != exe_dir]
        new_path = ";".join(parts)
        winreg.SetValueEx(env_key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(env_key)
        print("  PATH   -> 已从环境变量移除")
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, 0)
    except (OSError, FileNotFoundError):
        pass

    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass

    print()
    print("已全部移除。")


def pause():
    """等待用户按回车后关闭（非交互终端下跳过）"""
    if not sys.stdin.isatty():
        return
    print()
    try:
        input("按 Enter 键继续...")
    except (EOFError, KeyboardInterrupt):
        pass


def main():
    args = sys.argv[1:]

    if not args:
        cmd_repl()
        return

    # 检测 --fast 标志
    fast_mode = "--fast" in args
    if fast_mode:
        args = [a for a in args if a != "--fast"]

    # 子命令
    if args[0] == "run":
        if len(args) < 2:
            print("用法: zhiai run <文件.za|文件.zab> [--fast]", file=sys.stderr)
            sys.exit(1)
        filepath = args[1]
        if filepath.endswith(".zab"):
            cmd_run_zab(filepath, fast=fast_mode)
        else:
            cmd_run_za(filepath)
        pause()
        return

    if args[0] == "compile":
        if len(args) < 2:
            print("用法: zhiai compile <文件.za> [-o 输出.zab] [--exe] [--dll]", file=sys.stderr)
            sys.exit(1)
        input_file = args[1]
        
        is_exe = "--exe" in args
        is_dll = "--dll" in args
        
        # 过滤掉标志参数，以便提取 -o
        clean_args = [a for a in args if a not in ("--exe", "--dll")]
        
        output_file = None
        if "-o" in clean_args:
            idx = clean_args.index("-o")
            if idx + 1 < len(clean_args):
                output_file = clean_args[idx + 1]
                
        if is_exe:
            cmd_compile_exe(input_file, output_file)
        elif is_dll:
            print("正在将致爱模块编译为共享类库 (DLL)...")
            cmd_compile(input_file, output_file)
            print("模块类库编译完成，可通过 导入(\"模块名\") 在其他程序中使用。")
        else:
            cmd_compile(input_file, output_file)
            
        pause()
        return

    if args[0] == "exec":
        if len(args) < 2:
            print("用法: zhiai exec <文件.zab> [--fast]", file=sys.stderr)
            sys.exit(1)
        cmd_run_zab(args[1], fast=fast_mode)
        pause()
        return

    if args[0] == "-e":
        if len(args) < 2:
            print("用法: zhiai -e '代码'", file=sys.stderr)
            sys.exit(1)
        cmd_eval(args[1])
        return

    if args[0] in ("-h", "--help"):
        print(__doc__)
        return

    if args[0] in ("-v", "--version"):
        print("致爱 v1.0.1")
        return

    if args[0] == "install":
        cmd_install()
        pause()
        return

    if args[0] == "uninstall":
        cmd_uninstall()
        pause()
        return

    if args[0] == "zap":
        import zhiai_zap
        sys.argv = [sys.argv[0]] + args[1:]
        zhiai_zap.main()
        return

    if args[0] == "fmt":
        import zhiai_fmt
        sys.argv = [sys.argv[0]] + args[1:]
        zhiai_fmt.main()
        return

    if args[0] == "debug":
        if len(args) < 2:
            print("用法: zhiai debug <文件.zab>", file=sys.stderr)
            sys.exit(1)
        # 调试模式下运行，VM 会处理 BREAKPOINT
        cmd_run_zab(args[1], fast=False)
        return

    # 默认：根据扩展名自动判断
    jit = "--jit" in args
    if jit: args.remove("--jit")
    filepath = args[0]
    if not os.path.exists(filepath):
        print("错误: 文件不存在 '" + filepath + "'", file=sys.stderr)
        pause()
        sys.exit(1)

    if filepath.endswith(".zab"):
        cmd_run_zab(filepath, fast=fast_mode)
    elif filepath.endswith(".za"):
        cmd_compile_and_run(filepath, fast=fast_mode, jit=jit)
    else:
        print("错误: 不支持的文件类型 '" + filepath + "'", file=sys.stderr)
        print("支持: .za (源码) .zab (字节码)", file=sys.stderr)
        pause()
        sys.exit(1)
        pause()
        sys.exit(1)

    pause()


if __name__ == "__main__":
    main()
