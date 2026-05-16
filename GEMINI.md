# 致爱 (Zhiai) 编程语言

致爱 (Zhiai) 是一门以中文为语法的编程语言，旨在为中文母语者提供直观的编程体验。该项目包含完整的编译器、解释器、虚拟机以及配套的 VS Code 扩展。

## 项目概览

- **核心语言实现 (`zhiai/`)**: 使用 Python 编写，包含词法分析器 (`lexer.py`)、解析器 (`parser.py`)、AST 节点定义 (`ast_nodes.py`)、解释器 (`interpreter.py`) 和虚拟机 (`vm.py`)。
- **自举编译器 (`compiler/`)**: 使用致爱语言自身编写的编译器 (`main.za`)，可将 `.za` 源码编译为 `.zab` 字节码。
- **命令行工具 (`zhiai_cli.py`)**: 统一的入口点，支持 REPL、解释运行、编译字节码、打包 EXE 等功能。
- **VS Code 扩展 (`vscode-zhiai/`)**: 提供语法高亮和代码片段支持。
- **示例与测试 (`examples/`, `*.za`)**: 包含大量的语言特性演示和验证脚本。

## 运行与编译

项目主要通过 `zhiai_cli.py` (通常打包为 `zhiai.exe`) 进行操作。

### 基本命令

- **启动 REPL**: `zhiai`
- **解释运行**: `zhiai run <file.za>`
- **编译为字节码**: `zhiai compile <file.za> [-o output.zab]`
- **编译并运行**: `zhiai <file.za>` (自动处理编译与 VM 执行)
- **运行字节码**: `zhiai exec <file.zab>`
- **编译为独立 EXE**: `zhiai compile <file.za> --exe`
- **执行单行代码**: `zhiai -e '输出("你好")'`
- **注册文件关联 (Windows)**: `zhiai install`

### 开发与测试

- **全量测试**: 运行 `run_all.ps1` (PowerShell) 或 `run_all.bat`。该脚本会验证解释器模式、字节码模式以及自举编译器的正确性。
- **自举编译**: `python -m zhiai compiler/main.za compiler/main.za -o compiler.zab`
- **VS Code 扩展开发**:
  1. 进入 `vscode-zhiai/` 目录。
  2. 运行 `npm install`。
  3. 运行 `npm run compile` 进行编译。

## 技术架构

1.  **解释模式**: `Lexer` -> `Parser` -> `Interpreter` (Tree-walking)。适用于快速调试。
2.  **编译模式**: `Lexer` -> `Parser` -> `Compiler (main.za)` -> `.zab` (JSON 格式字节码)。
3.  **虚拟机模式**: `VM` 加载 `.zab` -> 执行指令流。提供更好的性能和闭包支持。

## 贡献与规范

- **语法标准**: 所有关键字、内置函数和方法均使用中文。
- **编码**: 源码文件强制使用 `UTF-8` 编码。
- **错误处理**: 语言支持 `尝试...捕获...结束` 机制。
- **扩展性**: 内置函数在 `zhiai/builtins.py` 中定义，可轻松扩展。

## 关键文件索引

- `zhiai_cli.py`: CLI 逻辑与打包入口。
- `zhiai/vm.py`: 虚拟机实现，处理指令集和作用域。
- `zhiai/interpreter.py`: 递归下降解释器。
- `compiler/main.za`: 核心编译逻辑，定义了从 AST 到字节码的转换。
- `vscode-zhiai/syntaxes/zhiai.tmLanguage.json`: 语法高亮定义。
