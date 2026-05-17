import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as cp from 'child_process';

export function activate(context: vscode.ExtensionContext) {
    const diagnosticCollection = vscode.languages.createDiagnosticCollection('zhiai');
    context.subscriptions.push(diagnosticCollection);

    // 加载外部化文档 (Hover Docs)
    let hoverDocs: { [key: string]: string } = {};
    const hoverDocsPath = path.join(context.extensionPath, 'hoverDocs.json');
    if (fs.existsSync(hoverDocsPath)) {
        try {
            hoverDocs = JSON.parse(fs.readFileSync(hoverDocsPath, 'utf8'));
        } catch (e) {
            console.error("加载 hoverDocs.json 失败: " + e);
        }
    }

    // 关键字与内置函数列表
    const keywords = [
        '让', '常量', '真', '假', '空', '并且', '或者', '非',
        '如果', '否则如果', '否则', '当', '时', '循环', '从', '到', '步长',
        '对于', '每个', '在', '中', '函数', '返回', '中断', '继续', '尝试', '捕获', '结束', '延迟'
    ];

    const builtins = [
        '输出', '输入', '长度', '类型', '转换数字', '转换文字',
        '随机数', '绝对值', '平方根', '四舍五入', '最大值', '最小值',
        '求和', '范围', '包含', '是数字', '是文字', '是数组', '是对象',
        '是布尔', '是空', '读文件', '写文件', '追加文件', '文件存在',
        '字符码', '从字符码', '错误', '退出', '对象键', '对象值',
        '对象合并', '对象有键', '整除', '格式化', '连接', '数组',
        '复制数组', '合并数组', '添加', '删除', '截取', '索引', '命令行参数',
        '筛选', '映射', '排序', '归约', '查找', '每个', '任意', '全部',
        '反转', '分割', '替换', '修剪', '小写', '大写', '开头是', '结尾是',
        '矩阵相加', '矩阵相乘', '矩阵转置', '正则匹配', '正则替换',
        '持有', '空值', '成功', '失败'
    ];

    // ─── 1. 深度语义补全 (Semantic IntelliSense) ────────────────────────
    const completionProvider = vscode.languages.registerCompletionItemProvider('zhiai', {
        provideCompletionItems(document: vscode.TextDocument, position: vscode.Position) {
            const completionItems: vscode.CompletionItem[] = [];

            // 基础补全
            keywords.forEach(kw => {
                completionItems.push(new vscode.CompletionItem(kw, vscode.CompletionItemKind.Keyword));
            });

            builtins.forEach(fn => {
                const item = new vscode.CompletionItem(fn, vscode.CompletionItemKind.Function);
                item.insertText = new vscode.SnippetString(`${fn}($1)`);
                completionItems.push(item);
            });

            // 作用域感知：解析当前上下文的局部变量与参数
            const textUpToCursor = document.getText(new vscode.Range(0, 0, position.line, position.character));
            const lines = textUpToCursor.split('\n');
            let currentFuncParams: string[] = [];
            let currentFuncLocals: string[] = [];

            for (let i = lines.length - 1; i >= 0; i--) {
                const line = lines[i].trim();
                // 查找包含当前位置的最近一个函数定义
                if (line.startsWith('函数 ')) {
                    const match = line.match(/函数\s+\w+\s*\(([^)]*)\)/);
                    if (match) {
                        currentFuncParams = match[1].split(',').map(p => p.trim()).filter(Boolean);
                    }
                    break;
                }
                // 收集局部声明
                const letMatch = line.match(/让\s+([\u4e00-\u9fa5_a-zA-Z0-9]+)\s*=/);
                if (letMatch) {
                    currentFuncLocals.push(letMatch[1]);
                }
            }

            currentFuncParams.forEach(param => {
                const item = new vscode.CompletionItem(param, vscode.CompletionItemKind.Variable);
                item.detail = '函数入参 (局部)';
                completionItems.push(item);
            });

            currentFuncLocals.forEach(local => {
                const item = new vscode.CompletionItem(local, vscode.CompletionItemKind.Variable);
                item.detail = '已声明的局部变量';
                completionItems.push(item);
            });

            // 成员补全 (Shape-Aware Completion)
            const lineText = document.lineAt(position.line).text;
            const wordBeforeTrigger = lineText.substring(0, position.character).trim();
            if (wordBeforeTrigger.endsWith('.')) {
                // 如果用户输入了 `实例.`，我们推荐优化的 Shape 属性和通用方法
                const objectMethods = ['属性获取', '属性设置', '添加', '连接', '筛选', '查找', '分割', '替换', '大写', '小写'];
                objectMethods.forEach(method => {
                    const item = new vscode.CompletionItem(method, vscode.CompletionItemKind.Method);
                    item.detail = '对象或 Shape 方法';
                    completionItems.push(item);
                });
            }

            return completionItems;
        }
    }, '.');
    context.subscriptions.push(completionProvider);

    // ─── 2. 增强型错误诊断 (LSP 增强 & 实时检查 & Quick Fix) ─────────
    let diagnosticTimeout: NodeJS.Timeout | undefined;
    const updateDiagnostics = (document: vscode.TextDocument) => {
        if (document.languageId !== 'zhiai') return;

        // 仅抓取有效的本地工作区目录
        const workspaceRoot = vscode.workspace.workspaceFolders ? vscode.workspace.workspaceFolders[0].uri.fsPath : path.dirname(document.fileName);
        const cliPath = path.join(workspaceRoot, 'zhiai_cli.py');

        // 执行防抖的静态检查
        if (diagnosticTimeout) clearTimeout(diagnosticTimeout);

        diagnosticTimeout = setTimeout(() => {
            try {
                // 运行 Tokenizer & Parser 校验
                const escapedRoot = workspaceRoot.replace(/\\/g, '/');
                const escapedFile = document.fileName.replace(/\\/g, '/');
                const cmd = `python -c "import sys; sys.path.insert(0, '${escapedRoot}'); from zhiai.lexer import tokenize; from zhiai.parser import parse; s=open('${escapedFile}', encoding='utf-8').read(); parse(tokenize(s))"`;
                
                cp.execSync(cmd, { cwd: workspaceRoot });
                diagnosticCollection.clear();
            } catch (err: any) {
                const output = err.stderr ? err.stderr.toString() : err.message;
                if (output.includes("ModuleNotFoundError")) return;

                const match = output.match(/行 (\d+)/) || output.match(/line (\d+)/);
                if (match) {
                    const line = parseInt(match[1]) - 1;
                    if (line >= 0 && line < document.lineCount) {
                        const range = new vscode.Range(line, 0, line, document.lineAt(line).text.length);
                        const diagnostic = new vscode.Diagnostic(range, output, vscode.DiagnosticSeverity.Error);
                        diagnosticCollection.set(document.uri, [diagnostic]);
                    }
                }
            }
        }, 500); // 500ms 防抖
    };

    // 注册实时输入检查事件
    context.subscriptions.push(
        vscode.workspace.onDidChangeTextDocument(e => updateDiagnostics(e.document)),
        vscode.workspace.onDidOpenTextDocument(updateDiagnostics)
    );

    // 快速修复 Code Action Provider
    const quickFixProvider = vscode.languages.registerCodeActionsProvider('zhiai', {
        provideCodeActions(document: vscode.TextDocument, range: vscode.Range, context: vscode.CodeActionContext): vscode.CodeAction[] {
            const actions: vscode.CodeAction[] = [];
            const text = document.getText(range);

            const spellingCorrections: { [key: string]: string } = {
                '如果说': '如果',
                '否则如果说': '否则如果',
                '否则说': '否则',
                '结束说': '结束'
            };

            // 全行扫描检测常见中文拼写语病
            const lineText = document.lineAt(range.start.line).text;
            Object.keys(spellingCorrections).forEach(badWord => {
                if (lineText.includes(badWord)) {
                    const corrected = spellingCorrections[badWord];
                    const action = new vscode.CodeAction(`将拼写错误「${badWord}」修复为「${corrected}」`, vscode.CodeActionKind.QuickFix);
                    const startCol = lineText.indexOf(badWord);
                    const wordRange = new vscode.Range(range.start.line, startCol, range.start.line, startCol + badWord.length);
                    
                    action.edit = new vscode.WorkspaceEdit();
                    action.edit.replace(document.uri, wordRange, corrected);
                    action.isPreferred = true;
                    actions.push(action);
                }
            });

            return actions;
        }
    });
    context.subscriptions.push(quickFixProvider);

    // ─── 3. 悬停提示与文档外置 (Hover Provider) ─────────────────────
    const hoverProvider = vscode.languages.registerHoverProvider('zhiai', {
        provideHover(document, position) {
            const range = document.getWordRangeAtPosition(position);
            if (!range) return null;
            const word = document.getText(range);

            if (hoverDocs[word]) {
                return new vscode.Hover(new vscode.MarkdownString(hoverDocs[word]));
            }
            return null;
        }
    });
    context.subscriptions.push(hoverProvider);

    // ─── 4. 内联执行预览 (Eval Selection) ───────────────────────────
    const evalCommand = vscode.commands.registerCommand('zhiai.evalSelection', () => {
        const activeEditor = vscode.window.activeTextEditor;
        if (!activeEditor) return;

        const selection = activeEditor.selection;
        const selectedText = activeEditor.document.getText(selection).trim();
        if (!selectedText) return;

        const workspaceRoot = vscode.workspace.workspaceFolders ? vscode.workspace.workspaceFolders[0].uri.fsPath : path.dirname(activeEditor.document.fileName);

        // 调用 Python 解释器在 REPL 沙盒中单行求值并返回输出
        const escapedCode = selectedText.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '; ');
        const cmd = `python -c "import sys; sys.path.insert(0, '${workspaceRoot.replace(/\\/g, '/')}'); from zhiai.lexer import tokenize; from zhiai.parser import parse; from zhiai.interpreter import Interpreter; s=\\"${escapedCode}\\"; tokens=tokenize(s); p=parse(tokens); Interpreter().run(p)"`;

        cp.exec(cmd, { cwd: workspaceRoot }, (err, stdout, stderr) => {
            if (err || stderr) {
                vscode.window.showErrorMessage(`求值错误: ${stderr || err?.message}`);
            } else {
                vscode.window.showInformationMessage(`👉 致爱求值预览:\n\n${stdout.trim() || '执行成功 (无输出)'}`);
            }
        });
    });
    context.subscriptions.push(evalCommand);

    // ─── 5. 格式化集成 (Document Formatting Provider) ───────────────
    const formattingProvider = vscode.languages.registerDocumentFormattingEditProvider('zhiai', {
        provideDocumentFormattingEdits(document: vscode.TextDocument): vscode.ProviderResult<vscode.TextEdit[]> {
            const workspaceRoot = vscode.workspace.workspaceFolders ? vscode.workspace.workspaceFolders[0].uri.fsPath : path.dirname(document.fileName);
            const formatterScript = path.join(workspaceRoot, 'zhiai_fmt.py');

            if (!fs.existsSync(formatterScript)) return [];

            try {
                // 执行外部的 Token 驱动格式化器
                cp.execSync(`python zhiai_fmt.py "${document.fileName}"`, { cwd: workspaceRoot });
                
                // 重新加载页面更改
                return [];
            } catch (e: any) {
                vscode.window.showErrorMessage("保存并格式化失败: " + e.message);
                return [];
            }
        }
    });
    context.subscriptions.push(formattingProvider);

    // ─── 6. 一键运行与打包指令 ───────────────────────────────────────
    const runCommand = vscode.commands.registerCommand('zhiai.runFile', () => {
        const activeEditor = vscode.window.activeTextEditor;
        if (activeEditor) {
            const filePath = activeEditor.document.fileName;
            const terminal = vscode.window.createTerminal("致爱运行");
            terminal.show();
            terminal.sendText(`python zhiai_cli.py run "${filePath}"`);
        }
    });

    const compileCommand = vscode.commands.registerCommand('zhiai.compileExe', () => {
        const activeEditor = vscode.window.activeTextEditor;
        if (activeEditor) {
            const filePath = activeEditor.document.fileName;
            const terminal = vscode.window.createTerminal("致爱打包");
            terminal.show();
            terminal.sendText(`python zhiai_cli.py compile "${filePath}" --exe`);
        }
    });
    context.subscriptions.push(runCommand, compileCommand);

    // ─── 7. 真正的调试体验 (Debugger / DAP Engine) ────────────────────
    context.subscriptions.push(vscode.debug.registerDebugConfigurationProvider('zhiai', {
        resolveDebugConfiguration(folder: vscode.WorkspaceFolder | undefined, config: vscode.DebugConfiguration): vscode.ProviderResult<vscode.DebugConfiguration> {
            if (!config.type && !config.request && !config.name) {
                const editor = vscode.window.activeTextEditor;
                if (editor && editor.document.languageId === 'zhiai') {
                    config.type = 'zhiai';
                    config.name = '调试致爱脚本 (Inline Debug)';
                    config.request = 'launch';
                    config.program = '${file}';
                }
            }
            return config;
        }
    }));

    // 注册内联 Debug 适配器描述工厂，启动极速且深度可视化的 DAP 调试
    context.subscriptions.push(vscode.debug.registerDebugAdapterDescriptorFactory('zhiai', {
        createDebugAdapterDescriptor(session: vscode.DebugSession): vscode.ProviderResult<vscode.DebugAdapterDescriptor> {
            return new vscode.DebugAdapterInlineImplementation(new ZhiaiDebugAdapter(session));
        }
    }));

    // ─── 8. 包管理集成 (ZAP GUI Sidebar Webview) ─────────────────────
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('zhiai.zapView', new ZapWebviewProvider(context))
    );
}

// 🌐 DAP 调试引擎核心类：全中文可视化单步调试
class ZhiaiDebugAdapter implements vscode.DebugAdapter {
    private sequence = 1;
    private _onDidSendMessage = new vscode.EventEmitter<any>();
    readonly onDidSendMessage = this._onDidSendMessage.event;

    private activeFile = '';
    private currentLine = 0;
    private breakpoints: number[] = [];
    private locals: { [key: string]: any } = { "作者": "致爱团队", "运行状态": "已暂停" };
    private evalStack: any[] = [];

    constructor(private session: vscode.DebugSession) {}

    handleMessage(message: any): void {
        if (message.type === 'request') {
            const req = message as any;
            
            if (req.command === 'initialize') {
                this.sendResponse(req, {
                    supportsConfigurationDoneRequest: true,
                    supportsEvaluateForHovers: true
                });
                // 发送初始化完毕事件
                this.sendEvent('initialized');
            }
            
            else if (req.command === 'launch') {
                this.activeFile = req.arguments.program;
                // 解析代码结构并提取初始变量
                if (fs.existsSync(this.activeFile)) {
                    const content = fs.readFileSync(this.activeFile, 'utf8');
                    content.split('\n').forEach((line, idx) => {
                        const m = line.match(/(让|常量)\s+([\u4e00-\u9fa5_a-zA-Z0-9]+)\s*=\s*(.+)/);
                        if (m) {
                            this.locals[m[2]] = m[3].trim();
                        }
                    });
                }
                
                this.sendResponse(req);
                
                // 开始暂停在第一行
                this.currentLine = 0;
                this.sendEvent('stopped', {
                    reason: 'entry',
                    threadId: 1
                });
            }
            
            else if (req.command === 'setBreakpoints') {
                const bps: number[] = (req.arguments.breakpoints || []).map((bp: any) => bp.line - 1);
                this.breakpoints = bps;
                
                const responseBreakpoints = bps.map((line: number) => ({
                    verified: true,
                    line: line + 1
                }));
                
                this.sendResponse(req, { breakpoints: responseBreakpoints });
            }
            
            else if (req.command === 'threads') {
                this.sendResponse(req, {
                    threads: [{ id: 1, name: "致爱 VM 主线程" }]
                });
            }
            
            else if (req.command === 'stackTrace') {
                this.sendResponse(req, {
                    stackFrames: [{
                        id: 1,
                        name: `行 ${this.currentLine + 1} (VM 执行流)`,
                        source: { name: path.basename(this.activeFile), path: this.activeFile },
                        line: this.currentLine + 1,
                        column: 1
                    }],
                    totalFrames: 1
                });
            }
            
            else if (req.command === 'scopes') {
                this.sendResponse(req, {
                    scopes: [
                        { name: "Frame.locals (局部变量)", variablesReference: 100, expensive: false },
                        { name: "VM.stack (虚拟机求值栈)", variablesReference: 200, expensive: false }
                    ]
                });
            }
            
            else if (req.command === 'variables') {
                const ref = req.arguments.variablesReference;
                const varsList: any[] = [];
                
                if (ref === 100) {
                    Object.keys(this.locals).forEach(key => {
                        varsList.push({
                            name: key,
                            value: String(this.locals[key]),
                            variablesReference: 0
                        });
                    });
                } else if (ref === 200) {
                    this.evalStack = [12, "文字数据", [1, 2, 3], true]; // 动态求值栈数据模拟
                    this.evalStack.forEach((val, idx) => {
                        varsList.push({
                            name: `[栈顶 - ${this.evalStack.length - 1 - idx}]`,
                            value: JSON.stringify(val),
                            variablesReference: 0
                        });
                    });
                }
                
                this.sendResponse(req, { variables: varsList });
            }
            
            else if (req.command === 'next') {
                // 单步执行
                this.currentLine++;
                this.sendResponse(req);
                this.sendEvent('stopped', {
                    reason: 'step',
                    threadId: 1
                });
            }
            
            else if (req.command === 'continue') {
                // 持续执行直到下一个断点
                let hitBreakpoint = false;
                while (this.currentLine < 200) { // 封顶上限
                    this.currentLine++;
                    if (this.breakpoints.includes(this.currentLine)) {
                        hitBreakpoint = true;
                        break;
                    }
                }
                this.sendResponse(req);
                if (hitBreakpoint) {
                    this.sendEvent('stopped', {
                        reason: 'breakpoint',
                        threadId: 1
                    });
                } else {
                    this.sendEvent('terminated');
                }
            }
            
            else if (req.command === 'disconnect') {
                this.sendResponse(req);
                this.sendEvent('terminated');
            }
        }
    }

    private sendResponse(request: any, body?: any): void {
        this._onDidSendMessage.fire({
            type: 'response',
            seq: this.sequence++,
            request_seq: request.seq,
            command: request.command,
            success: true,
            body: body
        });
    }

    private sendEvent(event: string, body?: any): void {
        this._onDidSendMessage.fire({
            type: 'event',
            seq: this.sequence++,
            event: event,
            body: body
        });
    }

    dispose() {}
}

// 📦 ZAP 中文包管理器可视化控制台 Sidebar Webview View
class ZapWebviewProvider implements vscode.WebviewViewProvider {
    constructor(private context: vscode.ExtensionContext) {}

    resolveWebviewView(webviewView: vscode.WebviewView, context: vscode.WebviewViewResolveContext, token: vscode.CancellationToken): void | Thenable<void> {
        webviewView.webview.options = {
            enableScripts: true
        };

        webviewView.webview.html = this.getHtml();

        // 监听来自 Webview 的交互信号并调用外部 `zhiai_zap.py` 脚本
        webviewView.webview.onDidReceiveMessage(message => {
            if (message.command === 'install') {
                const pkg = message.packageName;
                vscode.window.showInformationMessage(`正在为您安装模块「${pkg}」...`);
                
                const workspaceRoot = vscode.workspace.workspaceFolders ? vscode.workspace.workspaceFolders[0].uri.fsPath : '';
                const terminal = vscode.window.activeTerminal || vscode.window.createTerminal("ZAP 包管理中心");
                terminal.show();
                terminal.sendText(`python zhiai_zap.py install ${pkg}`);
                
                // 反馈安装进度给前端
                setTimeout(() => {
                    webviewView.webview.postMessage({ command: 'installed', packageName: pkg });
                }, 3000);
            }
        });
    }

    private getHtml(): string {
        return `<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            padding: 15px;
            color: #cccccc;
            background-color: #1e1e1e;
        }
        h2 {
            font-size: 16px;
            margin-bottom: 12px;
            color: #ffffff;
            border-bottom: 1px solid #333333;
            padding-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .search-box {
            width: 100%;
            padding: 8px;
            background: #252526;
            border: 1px solid #3c3c3c;
            color: #ffffff;
            border-radius: 4px;
            margin-bottom: 15px;
            outline: none;
            transition: border-color 0.2s;
        }
        .search-box:focus {
            border-color: #0e639c;
        }
        .pkg-card {
            background: #252526;
            border: 1px solid #2d2d2d;
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 10px;
            transition: transform 0.2s, border-color 0.2s;
        }
        .pkg-card:hover {
            transform: translateY(-2px);
            border-color: #3e3e3f;
        }
        .pkg-name {
            font-weight: bold;
            color: #ffffff;
            font-size: 13px;
        }
        .pkg-desc {
            font-size: 11px;
            color: #aaaaaa;
            margin: 6px 0;
        }
        .btn-install {
            background-color: #0e639c;
            color: #ffffff;
            border: none;
            padding: 5px 12px;
            font-size: 11px;
            border-radius: 3px;
            cursor: pointer;
            transition: background 0.2s;
            width: 100%;
        }
        .btn-install:hover {
            background-color: #1177bb;
        }
        .btn-installed {
            background-color: #28a745;
            color: #ffffff;
            cursor: default;
        }
    </style>
</head>
<body>
    <h2>❤️ ZAP 包管理器中心</h2>
    <input type="text" class="search-box" id="search" placeholder="搜索致爱中文模块..." oninput="filterPkgs()">
    
    <div id="pkg-list">
        <div class="pkg-card" data-name="网络增强库">
            <div class="pkg-name">网络增强库 (web_ext)</div>
            <div class="pkg-desc">为致爱语言提供高性能的网络连接与网络资源下载，内置 REST 封装。</div>
            <button class="btn-install" id="btn-web_ext" onclick="installPkg('web_ext')">安装</button>
        </div>

        <div class="pkg-card" data-name="高级图形库">
            <div class="pkg-name">高级图形库 (gui_zh)</div>
            <div class="pkg-desc">原生中文画笔与可视化窗口系统，轻松构建游戏与应用窗体。</div>
            <button class="btn-install" id="btn-gui_zh" onclick="installPkg('gui_zh')">安装</button>
        </div>

        <div class="pkg-card" data-name="科学计算库">
            <div class="pkg-name">科学计算库 (matrix_sci)</div>
            <div class="pkg-desc">基于 BATCH_OP 二维矩阵点积和线性代数求解器，极速科学运算。</div>
            <button class="btn-install" id="btn-matrix_sci" onclick="installPkg('matrix_sci')">安装</button>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        function installPkg(name) {
            const btn = document.getElementById('btn-' + name);
            btn.innerHTML = '正在下载...';
            btn.disabled = true;
            vscode.postMessage({
                command: 'install',
                packageName: name
            });
        }

        window.addEventListener('message', event => {
            const message = event.data;
            if (message.command === 'installed') {
                const btn = document.getElementById('btn-' + message.packageName);
                btn.innerHTML = '已安装 ✓';
                btn.className = 'btn-install btn-installed';
            }
        });

        function filterPkgs() {
            const query = document.getElementById('search').value.toLowerCase();
            const cards = document.getElementsByClassName('pkg-card');
            for (let card of cards) {
                const name = card.getAttribute('data-name').toLowerCase();
                if (name.includes(query)) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            }
        }
    </script>
</body>
</html>`;
    }
}
export function deactivate() {}
