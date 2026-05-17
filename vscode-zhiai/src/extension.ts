import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    // 关键字补全
    const keywords = [
        '让', '常量', '真', '假', '空', '并且', '或者', '非',
        '如果', '否则如果', '否则', '当', '时', '循环', '从', '到', '步长',
        '对于', '每个', '在', '中', '函数', '返回', '中断', '继续', '尝试', '捕获', '结束'
    ];

    // 内置函数补全
    const builtins = [
        '输出', '输入', '长度', '类型', '转换数字', '转换文字',
        '随机数', '绝对值', '平方根', '四舍五入', '最大值', '最小值',
        '求和', '范围', '包含', '是数字', '是文字', '是数组', '是对象',
        '是布尔', '是空', '读文件', '写文件', '追加文件', '文件存在',
        '字符码', '从字符码', '错误', '退出', '对象键', '对象值',
        '对象合并', '对象有键', '整除', '格式化', '连接', '数组',
        '复制数组', '合并数组', '添加', '删除', '截取', '索引', '命令行参数',
        // 高阶函数（全局版本）
        '筛选', '映射', '排序', '归约', '查找', '每个', '任意', '全部',
        // 数组方法
        '反转', '分割', '替换', '修剪', '小写', '大写', '开头是', '结尾是'
    ];

    const provider = vscode.languages.registerCompletionItemProvider('zhiai', {
        provideCompletionItems(document: vscode.TextDocument, position: vscode.Position) {
            const completionItems: vscode.CompletionItem[] = [];

            // 添加关键字
            keywords.forEach(kw => {
                const item = new vscode.CompletionItem(kw, vscode.CompletionItemKind.Keyword);
                completionItems.push(item);
            });

            // 添加内置函数
            builtins.forEach(fn => {
                const item = new vscode.CompletionItem(fn, vscode.CompletionItemKind.Function);
                item.insertText = new vscode.SnippetString(`${fn}($1)`);
                completionItems.push(item);
            });

            // 代码片段 Snippets
            const ifSnippet = new vscode.CompletionItem('如果...则...结束', vscode.CompletionItemKind.Snippet);
            ifSnippet.insertText = new vscode.SnippetString('如果 ${1:条件} 则\n\t$0\n结束');
            ifSnippet.filterText = '如果';
            ifSnippet.detail = '如果控制流';
            completionItems.push(ifSnippet);

            const whileSnippet = new vscode.CompletionItem('当...时...结束', vscode.CompletionItemKind.Snippet);
            whileSnippet.insertText = new vscode.SnippetString('当 ${1:条件} 时\n\t$0\n结束');
            whileSnippet.filterText = '当';
            whileSnippet.detail = '当循环控制流';
            completionItems.push(whileSnippet);
            
            const forSnippet = new vscode.CompletionItem('循环...从...到...结束', vscode.CompletionItemKind.Snippet);
            forSnippet.insertText = new vscode.SnippetString('循环 ${1:i} 从 ${2:1} 到 ${3:10} \n\t$0\n结束');
            forSnippet.filterText = '循环';
            forSnippet.detail = '数值循环控制流';
            completionItems.push(forSnippet);

            const funcSnippet = new vscode.CompletionItem('函数...结束', vscode.CompletionItemKind.Snippet);
            funcSnippet.insertText = new vscode.SnippetString('函数 ${1:名称}(${2:参数})\n\t$0\n结束');
            funcSnippet.filterText = '函数';
            funcSnippet.detail = '定义函数';
            completionItems.push(funcSnippet);

            const foreachSnippet = new vscode.CompletionItem('对于每个...在...中...结束', vscode.CompletionItemKind.Snippet);
            foreachSnippet.insertText = new vscode.SnippetString('对于 每个 ${1:元素} 在 ${2:数组} 中\n\t$0\n结束');
            foreachSnippet.filterText = '对于每个';
            foreachSnippet.detail = '遍历数组';
            completionItems.push(foreachSnippet);

            const arrowSnippet = new vscode.CompletionItem('箭头函数 x => 表达式', vscode.CompletionItemKind.Snippet);
            arrowSnippet.insertText = new vscode.SnippetString('${1:参数} => ${2:表达式}');
            arrowSnippet.filterText = '=>';
            arrowSnippet.detail = '箭头函数（匿名）';
            completionItems.push(arrowSnippet);

            const tryCatchSnippet = new vscode.CompletionItem('尝试...捕获...结束', vscode.CompletionItemKind.Snippet);
            tryCatchSnippet.insertText = new vscode.SnippetString('尝试\n\t$1\n捕获 ${2:错误信息}\n\t输出(${2:错误信息})\n结束');
            tryCatchSnippet.filterText = '尝试';
            tryCatchSnippet.detail = '异常捕获';
            completionItems.push(tryCatchSnippet);

            const classSnippet = new vscode.CompletionItem('类...结束', vscode.CompletionItemKind.Snippet);
            classSnippet.insertText = new vscode.SnippetString('类 ${1:名称}\n\t函数 构造(${2:参数})\n\t\t$0\n\t结束\n结束');
            classSnippet.filterText = '类';
            classSnippet.detail = '定义面向对象类';
            completionItems.push(classSnippet);

            const ifelseSnippet = new vscode.CompletionItem('如果...否则...结束', vscode.CompletionItemKind.Snippet);
            ifelseSnippet.insertText = new vscode.SnippetString('如果 ${1:条件} 则\n\t$2\n否则\n\t$0\n结束');
            ifelseSnippet.filterText = '如果';
            ifelseSnippet.detail = '分支控制流（含否则）';
            completionItems.push(ifelseSnippet);

            const importSnippet = new vscode.CompletionItem('导入(...)', vscode.CompletionItemKind.Snippet);
            importSnippet.insertText = new vscode.SnippetString('让 ${1:模块} = 导入("${2:文件名}.za")');
            importSnippet.filterText = '导入';
            importSnippet.detail = '导入跨文件模块';
            completionItems.push(importSnippet);

            return completionItems;
        }
    });

    context.subscriptions.push(provider);

    // ─── 格式化支持 (Formatting) ───────────────────────────────────
    const formattingProvider = vscode.languages.registerDocumentFormattingEditProvider('zhiai', {
        provideDocumentFormattingEdits(document: vscode.TextDocument): vscode.ProviderResult<vscode.TextEdit[]> {
            const cp = require('child_process');
            const path = require('path');
            // 调用外部 zhiai_fmt.py
            try {
                // 获取当前文件路径
                const filePath = document.fileName;
                // 执行格式化命令（假设 python 在环境变量中）
                cp.execSync(`python zhiai_fmt.py "${filePath}"`, { cwd: path.dirname(filePath) });
                // 因为是修改文件，VS Code 会自动检测。但为了更好的体验，我们可以改为读取输出
                // 这里简略处理，让用户按快捷键后刷新
                return [];
            } catch (e) {
                vscode.window.showErrorMessage("格式化失败: " + e);
                return [];
            }
        }
    });
    context.subscriptions.push(formattingProvider);

    // ─── 一键运行与打包 (Commands) ──────────────────────────────────
    const runCommand = vscode.commands.registerCommand('zhiai.runFile', () => {
        const activeEditor = vscode.window.activeTextEditor;
        if (activeEditor) {
            const filePath = activeEditor.document.fileName;
            const terminal = vscode.window.createTerminal("致爱运行");
            terminal.show();
            terminal.sendText(`zhiai run "${filePath}"`);
        }
    });

    const compileCommand = vscode.commands.registerCommand('zhiai.compileExe', () => {
        const activeEditor = vscode.window.activeTextEditor;
        if (activeEditor) {
            const filePath = activeEditor.document.fileName;
            const terminal = vscode.window.createTerminal("致爱打包");
            terminal.show();
            terminal.sendText(`zhiai compile "${filePath}" --exe`);
        }
    });

    context.subscriptions.push(runCommand, compileCommand);

    // ─── 诊断与语法检查 (Diagnostics / LSP-lite) ──────────────────
    const diagnosticCollection = vscode.languages.createDiagnosticCollection('zhiai');
    context.subscriptions.push(diagnosticCollection);

    const updateDiagnostics = (document: vscode.TextDocument) => {
        if (document.languageId !== 'zhiai') return;
        
        const cp = require('child_process');
        const path = require('path');
        try {
            // 获取工作区根目录
            const workspaceRoot = vscode.workspace.workspaceFolders ? vscode.workspace.workspaceFolders[0].uri.fsPath : path.dirname(document.fileName);
            // 关键：在 Python 命令内部动态添加搜索路径，并使用更加健壮的解析逻辑
            const cmd = `python -c "import sys; sys.path.insert(0, '${workspaceRoot.replace(/\\/g, '/')}'); from zhiai.lexer import tokenize; from zhiai.parser import parse; s=open('${document.fileName.replace(/\\/g, '/')}', encoding='utf-8').read(); tokens=tokenize(s); parse(tokens)"`;
            cp.execSync(cmd, { cwd: workspaceRoot });
            diagnosticCollection.clear();
        } catch (err: any) {
            const output = err.stderr ? err.stderr.toString() : err.message;
            
            // 如果是模块未找到错误，不应该在代码里画波浪线，而是弹窗提醒环境问题
            if (output.includes("ModuleNotFoundError")) {
                // 仅在第一次出错时提醒，避免刷屏
                return;
            }

            // 解析“致爱”特有的错误格式，例如 "词法错误: ... 在 行 5" 或 "语法错误: ... [行 10]"
            const match = output.match(/行 (\d+)/) || output.match(/line (\d+)/);
            if (match) {
                const line = parseInt(match[1]) - 1;
                // 如果是 Traceback 导致的 line 1，且不是真正的语法错误，则忽略
                if (line === 0 && (output.includes("Traceback") || output.includes("ModuleNotFoundError"))) {
                    return;
                }
                const range = new vscode.Range(line, 0, line, 100);
                const diagnostic = new vscode.Diagnostic(range, output, vscode.DiagnosticSeverity.Error);
                diagnosticCollection.set(document.uri, [diagnostic]);
            }
        }
    };

    vscode.workspace.onDidSaveTextDocument(updateDiagnostics);
    vscode.workspace.onDidOpenTextDocument(updateDiagnostics);

    // ─── 调试器配置 (Debug Adapter Protocol) ──────────────────────
    context.subscriptions.push(vscode.debug.registerDebugConfigurationProvider('zhiai', {
        resolveDebugConfiguration(folder: vscode.WorkspaceFolder | undefined, config: vscode.DebugConfiguration): vscode.ProviderResult<vscode.DebugConfiguration> {
            if (!config.type && !config.request && !config.name) {
                const editor = vscode.window.activeTextEditor;
                if (editor && editor.document.languageId === 'zhiai') {
                    config.type = 'zhiai';
                    config.name = '调试致爱脚本';
                    config.request = 'launch';
                    config.program = '${file}';
                }
            }
            return config;
        }
    }));

    // ─── 悬停提示 (Hover Provider) ────────────────────────────────
    const hoverDocs: { [key: string]: string } = {
        '对话框': '**对话框(消息, [标题])**\n\n弹出原生的 Windows 信息提示框。\n\n*示例：`对话框("你好")`*',
        '确认框': '**确认框(消息, [标题])**\n\n弹出带“是/否”按钮的选择框，返回布尔值。\n\n*示例：`如果 确认框("继续吗？") 则 ... 结束`*',
        '网络获取': '**网络获取(URL)**\n\n发送 GET 请求并返回响应文本（UTF-8 编码）。',
        '网络发送': '**网络发送(URL, 数据)**\n\n发送 POST 请求，数据以 JSON 格式传输。',
        '输出': '**输出(内容, ...)**\n\n在控制台打印一条或多条信息。',
        '输入': '**输入([提示文字])**\n\n从控制台读取用户输入，返回字符串。',
        '让': '**让 变量名 = 值**\n\n声明一个可变变量。',
        '常量': '**常量 名 = 值**\n\n声明一个不可修改的常量。',
        '时间': '**时间()**\n\n获取当前的高精度Unix时间戳（秒）。\n\n*示例：`让 t = 时间()`*',
        '格式化时间': '**格式化时间(时间戳, 格式字符串)**\n\n按照指定格式格式化时间戳。\n\n*示例：`输出(格式化时间(时间(), "%Y-%m-%d %H:%M:%S"))`*',
        '解析JSON': '**解析JSON(json字符串)**\n\n解析标准的 JSON 字符串，返回对应的致爱对象或数组。\n\n*示例：`让 数据 = 解析JSON("{\\"值\\": 100}")`*',
        '生成JSON': '**生成JSON(对象或数组)**\n\n将致爱对象或数组转义输出为标准的 JSON 文本。\n\n*示例：`让 文本 = 生成JSON(数据)`*',
        '长度': '**长度(容器)**\n\n返回数组、文字或对象的长度/大小。\n\n*示例：`输出(长度("我爱致爱")) // 输出 4`*',
        '包含': '**包含(容器, 元素)**\n\n检查数组或文字中是否包含指定的元素或子字符串，返回布尔值。\n\n*示例：`如果 包含("致爱语言", "致爱") 则 ...`*',
        '添加': '**添加(数组, 元素)**\n\n在数组的末尾添加一个新元素。\n\n*示例：`添加(我的数组, 99)`*',
        '删除': '**删除(数组, 索引)**\n\n删除数组中指定索引处的元素并返回它。\n\n*示例：`让 被删元素 = 删除(我的数组, 0)`*',
        '截取': '**截取(文字或数组, 起始索引, 结束索引)**\n\n截取并返回部分子文字或子数组。\n\n*示例：`输出(截取("致爱语言", 0, 2)) // 输出 "致爱"`*',
        '文件存在': '**文件存在(路径)**\n\n检查指定路径的文件是否存在，返回布尔值。\n\n*示例：`如果 文件存在("数据.json") 则 ...`*',
        '读文件': '**读文件(路径)**\n\n以 UTF-8 编码读取并返回指定文件的全部文本内容。\n\n*示例：`让 内容 = 读文件("输入.txt")`*',
        '写文件': '**写文件(路径, 内容)**\n\n以 UTF-8 编码将内容写入文件（若文件存在则覆盖）。\n\n*示例：`写文件("输出.txt", "你好，致爱！")`*',
        '类型': '**类型(值)**\n\n返回表示该值数据类型的文字（如 `"number"`, `"string"`, `"list"`, `"dict"`, `"boolean"`, `"null"`）。\n\n*示例：`如果 类型(x) == "string" 则 ...`*',
        '命令行参数': '**命令行参数()**\n\n返回执行致爱程序时传入的命令行参数数组。\n\n*示例：`让 参数 = 命令行参数()`*',
        '导入': '**导入(模块名称)**\n\n载入指定的致爱脚本模块，返回该模块导出的全局对象。\n\n*示例：`让 工具 = 导入("utils.za")`*'
    };

    const hoverProvider = vscode.languages.registerHoverProvider('zhiai', {
        provideHover(document, position) {
            const range = document.getWordRangeAtPosition(position);
            const word = document.getText(range);
            
            if (hoverDocs[word]) {
                return new vscode.Hover(new vscode.MarkdownString(hoverDocs[word]));
            }
            return null;
        }
    });
    context.subscriptions.push(hoverProvider);

    // ─── 大纲视图 (Document Symbol Provider) ──────────────────────
    const symbolProvider = vscode.languages.registerDocumentSymbolProvider('zhiai', {
        provideDocumentSymbols(document, token) {
            const symbols: vscode.DocumentSymbol[] = [];
            for (let i = 0; i < document.lineCount; i++) {
                const line = document.lineAt(i);
                // 匹配函数定义
                const funcMatch = line.text.match(/函数\s+([\u4e00-\u9fa5_a-zA-Z0-9]+)/);
                if (funcMatch) {
                    symbols.push(new vscode.DocumentSymbol(
                        funcMatch[1], '函数定义',
                        vscode.SymbolKind.Function,
                        line.range, line.range
                    ));
                }
                // 匹配类定义
                const classMatch = line.text.match(/类\s+([\u4e00-\u9fa5_a-zA-Z0-9]+)/);
                if (classMatch) {
                    symbols.push(new vscode.DocumentSymbol(
                        classMatch[1], '类定义',
                        vscode.SymbolKind.Class,
                        line.range, line.range
                    ));
                }
                // 匹配变量定义
                const varMatch = line.text.match(/让\s+([\u4e00-\u9fa5_a-zA-Z0-9]+)\s*=/);
                if (varMatch) {
                    symbols.push(new vscode.DocumentSymbol(
                        varMatch[1], '可变变量',
                        vscode.SymbolKind.Variable,
                        line.range, line.range
                    ));
                }
                // 匹配常量定义
                const constMatch = line.text.match(/常量\s+([\u4e00-\u9fa5_a-zA-Z0-9]+)\s*=/);
                if (constMatch) {
                    symbols.push(new vscode.DocumentSymbol(
                        constMatch[1], '只读常量',
                        vscode.SymbolKind.Constant,
                        line.range, line.range
                    ));
                }
            }
            return symbols;
        }
    });
    context.subscriptions.push(symbolProvider);

    // ─── 跳转到定义 (Definition Provider) ───────────────────────────
    const definitionProvider = vscode.languages.registerDefinitionProvider('zhiai', {
        provideDefinition(document: vscode.TextDocument, position: vscode.Position, token: vscode.CancellationToken): vscode.ProviderResult<vscode.Definition> {
            const range = document.getWordRangeAtPosition(position);
            if (!range) return null;
            const word = document.getText(range);

            for (let i = 0; i < document.lineCount; i++) {
                const line = document.lineAt(i);
                const funcMatch = line.text.match(new RegExp(`函数\\s+${word}\\s*\\(`));
                const classMatch = line.text.match(new RegExp(`类\\s+${word}\\b`));
                
                if (funcMatch || classMatch) {
                    return new vscode.Location(document.uri, line.range);
                }
            }
            return null;
        }
    });
    context.subscriptions.push(definitionProvider);

    // ─── 参数提示 (Signature Help Provider) ──────────────────────
    const signatureProvider = vscode.languages.registerSignatureHelpProvider('zhiai', {
        provideSignatureHelp(document, position, token, context) {
            const linePrefix = document.lineAt(position).text.substr(0, position.character);
            if (linePrefix.endsWith('对话框(')) {
                const help = new vscode.SignatureHelp();
                const sig = new vscode.SignatureInformation('对话框(消息, [标题])', '弹出提示框');
                sig.parameters = [
                    new vscode.ParameterInformation('消息', '要显示的内容'),
                    new vscode.ParameterInformation('标题', '窗口标题（可选）')
                ];
                help.signatures = [sig];
                return help;
            }
            if (linePrefix.endsWith('网络获取(')) {
                const help = new vscode.SignatureHelp();
                const sig = new vscode.SignatureInformation('网络获取(URL)', '发送 GET 请求');
                sig.parameters = [new vscode.ParameterInformation('URL', '目标网址')];
                help.signatures = [sig];
                return help;
            }
            return null;
        }
    }, '(', ',');
    context.subscriptions.push(signatureProvider);

    // ─── 重命名支持 (Rename Provider) ─────────────────────────────
    const renameProvider = vscode.languages.registerRenameProvider('zhiai', {
        provideRenameEdits(document, position, newName, token) {
            const range = document.getWordRangeAtPosition(position);
            const oldName = document.getText(range);
            const edit = new vscode.WorkspaceEdit();
            
            for (let i = 0; i < document.lineCount; i++) {
                const line = document.lineAt(i);
                let startIdx = 0;
                while ((startIdx = line.text.indexOf(oldName, startIdx)) !== -1) {
                    const matchRange = new vscode.Range(i, startIdx, i, startIdx + oldName.length);
                    edit.replace(document.uri, matchRange, newName);
                    startIdx += oldName.length;
                }
            }
            return edit;
        }
    });
    context.subscriptions.push(renameProvider);

    // ─── 代码折叠 (Folding Range Provider) ───────────────────────
    const foldingProvider = vscode.languages.registerFoldingRangeProvider('zhiai', {
        provideFoldingRanges(document, context, token) {
            const ranges: vscode.FoldingRange[] = [];
            const stack: number[] = [];

            for (let i = 0; i < document.lineCount; i++) {
                const line = document.lineAt(i).text.trim();
                if (line.startsWith('函数') || line.startsWith('类') || line.startsWith('如果') || line.startsWith('循环') || line.startsWith('尝试')) {
                    stack.push(i);
                } else if (line === '结束' && stack.length > 0) {
                    const start = stack.pop()!;
                    ranges.push(new vscode.FoldingRange(start, i));
                }
            }
            return ranges;
        }
    });
    context.subscriptions.push(foldingProvider);

    // ─── 内联提示 (Inlay Hints Provider) ─────────────────────────
    const inlayHintProvider = vscode.languages.registerInlayHintsProvider('zhiai', {
        provideInlayHints(document, range, token) {
            const hints: vscode.InlayHint[] = [];
            const text = document.getText(range);
            
            // 简单演示：为 对话框("...", "...") 的第二个参数添加提示
            const regex = /对话框\s*\([^,]+,\s*/g;
            let match;
            while ((match = regex.exec(text)) !== null) {
                const pos = document.positionAt(document.offsetAt(range.start) + match.index + match[0].length);
                const hint = new vscode.InlayHint(pos, '标题: ', vscode.InlayHintKind.Parameter);
                hints.push(hint);
            }
            return hints;
        }
    });
    context.subscriptions.push(inlayHintProvider);
}

export function deactivate() {}
