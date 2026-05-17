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
        '对于', '每个', '在', '中', '函数', '返回', '中断', '继续', '尝试', '捕获', '结束', '延迟', '类', '新', '异步', '等待'
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
        '持有', '空值', '成功', '失败', '数据库连接'
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
                if (line.startsWith('函数 ') || line.startsWith('异步 函数 ')) {
                    const match = line.match(/函数\s+([\u4e00-\u9fa5_a-zA-Z0-9]+)\s*\(([^)]*)\)/);
                    if (match) {
                        currentFuncParams = match[2].split(',').map(p => p.trim()).filter(Boolean);
                    }
                    break;
                }
                const letMatch = line.match(/(让|常量)\s+([\u4e00-\u9fa5_a-zA-Z0-9]+)\s*=/);
                if (letMatch) {
                    currentFuncLocals.push(letMatch[2]);
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
                const objectMethods = ['添加', '连接', '筛选', '查找', '分割', '替换', '大写', '小写', '长度', '执行', '查询', '关闭', '获取', '取值', '是空', '是有', '发送', '接收'];
                objectMethods.forEach(method => {
                    const item = new vscode.CompletionItem(method, vscode.CompletionItemKind.Method);
                    completionItems.push(item);
                });
            }

            return completionItems;
        }
    }, '.');
    context.subscriptions.push(completionProvider);

    // ─── 2. 增强型错误诊断 ───────────────────────────────────────────
    let diagnosticTimeout: NodeJS.Timeout | undefined;
    const updateDiagnostics = (document: vscode.TextDocument) => {
        if (document.languageId !== 'zhiai') return;
        const workspaceRoot = vscode.workspace.workspaceFolders ? vscode.workspace.workspaceFolders[0].uri.fsPath : path.dirname(document.fileName);
        if (diagnosticTimeout) clearTimeout(diagnosticTimeout);

        diagnosticTimeout = setTimeout(() => {
            try {
                const escapedRoot = workspaceRoot.replace(/\\/g, '/');
                const escapedFile = document.fileName.replace(/\\/g, '/');
                const cmd = `python -c "import sys; sys.path.insert(0, '${escapedRoot}'); from zhiai.lexer import tokenize; from zhiai.parser import parse; s=open('${escapedFile}', encoding='utf-8').read(); parse(tokenize(s))"`;
                cp.execSync(cmd, { cwd: workspaceRoot });
                diagnosticCollection.clear();
            } catch (err: any) {
                const output = err.stderr ? err.stderr.toString() : err.message;
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
        }, 500);
    };

    context.subscriptions.push(
        vscode.workspace.onDidChangeTextDocument(e => updateDiagnostics(e.document)),
        vscode.workspace.onDidOpenTextDocument(updateDiagnostics)
    );

    // ─── 3. 大纲视图 (Document Symbol Provider) ──────────────────────
    const symbolProvider = vscode.languages.registerDocumentSymbolProvider('zhiai', {
        provideDocumentSymbols(document: vscode.TextDocument): vscode.DocumentSymbol[] {
            const symbols: vscode.DocumentSymbol[] = [];
            for (let i = 0; i < document.lineCount; i++) {
                const line = document.lineAt(i);
                // 匹配函数
                const funcMatch = line.text.match(/^(?:异步\s+)?函数\s+([\u4e00-\u9fa5_a-zA-Z0-9]+)/);
                if (funcMatch) {
                    symbols.push(new vscode.DocumentSymbol(funcMatch[1], '函数', vscode.SymbolKind.Function, line.range, line.range));
                    continue;
                }
                // 匹配类
                const classMatch = line.text.match(/^类\s+([\u4e00-\u9fa5_a-zA-Z0-9]+)/);
                if (classMatch) {
                    symbols.push(new vscode.DocumentSymbol(classMatch[1], '类', vscode.SymbolKind.Class, line.range, line.range));
                    continue;
                }
                // 匹配全局常量
                const constMatch = line.text.match(/^常量\s+([\u4e00-\u9fa5_a-zA-Z0-9]+)/);
                if (constMatch) {
                    symbols.push(new vscode.DocumentSymbol(constMatch[1], '常量', vscode.SymbolKind.Constant, line.range, line.range));
                }
            }
            return symbols;
        }
    });
    context.subscriptions.push(symbolProvider);

    // ─── 4. 跳转定义 (Definition Provider) ──────────────────────────
    const definitionProvider = vscode.languages.registerDefinitionProvider('zhiai', {
        provideDefinition(document: vscode.TextDocument, position: vscode.Position): vscode.ProviderResult<vscode.Definition> {
            const range = document.getWordRangeAtPosition(position);
            const word = document.getText(range);
            for (let i = 0; i < document.lineCount; i++) {
                const line = document.lineAt(i);
                if (line.text.includes(`函数 ${word}`) || line.text.includes(`类 ${word}`) || line.text.includes(`让 ${word}`) || line.text.includes(`常量 ${word}`)) {
                    return new vscode.Location(document.uri, line.range);
                }
            }
            return null;
        }
    });
    context.subscriptions.push(definitionProvider);

    // ─── 5. 重命名 (Rename Provider) ─────────────────────────────────
    const renameProvider = vscode.languages.registerRenameProvider('zhiai', {
        provideRenameEdits(document: vscode.TextDocument, position: vscode.Position, newName: string): vscode.WorkspaceEdit {
            const edit = new vscode.WorkspaceEdit();
            const range = document.getWordRangeAtPosition(position);
            const oldName = document.getText(range);
            const regex = new RegExp(`\\b${oldName}\\b`, 'g');
            for (let i = 0; i < document.lineCount; i++) {
                const line = document.lineAt(i);
                let m;
                while ((m = regex.exec(line.text)) !== null) {
                    const editRange = new vscode.Range(i, m.index, i, m.index + oldName.length);
                    edit.replace(document.uri, editRange, newName);
                }
            }
            return edit;
        }
    });
    context.subscriptions.push(renameProvider);

    // ─── 6. 参数提示 (Signature Help Provider) ───────────────────────
    const signatureProvider = vscode.languages.registerSignatureHelpProvider('zhiai', {
        provideSignatureHelp(document: vscode.TextDocument, position: vscode.Position): vscode.SignatureHelp {
            const lineText = document.lineAt(position.line).text;
            const openParenIndex = lineText.lastIndexOf('(', position.character);
            if (openParenIndex === -1) return new vscode.SignatureHelp();

            const wordRange = document.getWordRangeAtPosition(new vscode.Position(position.line, openParenIndex - 1));
            const funcName = document.getText(wordRange);

            const help = new vscode.SignatureHelp();
            // 查找定义以获取参数
            for (let i = 0; i < document.lineCount; i++) {
                const line = document.lineAt(i).text;
                const m = line.match(new RegExp(`函数\\s+${funcName}\\s*\\(([^)]*)\\)`));
                if (m) {
                    const signature = new vscode.SignatureInformation(`${funcName}(${m[1]})`, '致爱自定义函数');
                    signature.parameters = m[1].split(',').map(p => new vscode.ParameterInformation(p.trim()));
                    help.signatures.push(signature);
                    help.activeSignature = 0;
                    help.activeParameter = lineText.substring(openParenIndex, position.character).split(',').length - 1;
                    break;
                }
            }
            return help;
        }
    }, '(', ',');
    context.subscriptions.push(signatureProvider);

    // ─── 7. 其他现有功能 (Hover, Eval, Fmt, Commands, Debug, ZAP) ─────
    context.subscriptions.push(vscode.languages.registerHoverProvider('zhiai', {
        provideHover(document, position) {
            const range = document.getWordRangeAtPosition(position);
            if (!range) return null;
            const word = document.getText(range);
            if (hoverDocs[word]) return new vscode.Hover(new vscode.MarkdownString(hoverDocs[word]));
            return null;
        }
    }));

    context.subscriptions.push(vscode.commands.registerCommand('zhiai.evalSelection', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
        const text = editor.document.getText(editor.selection).trim();
        if (!text) return;
        const root = vscode.workspace.workspaceFolders ? vscode.workspace.workspaceFolders[0].uri.fsPath : path.dirname(editor.document.fileName);
        const escapedCode = text.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '; ');
        const cmd = `python -c "import sys; sys.path.insert(0, '${root.replace(/\\/g, '/')}'); from zhiai.lexer import tokenize; from zhiai.parser import parse; from zhiai.interpreter import Interpreter; s=\\"${escapedCode}\\"; Interpreter().run(parse(tokenize(s)))"`;
        cp.exec(cmd, { cwd: root }, (err, stdout, stderr) => {
            if (err || stderr) vscode.window.showErrorMessage(`求值错误: ${stderr || err?.message}`);
            else vscode.window.showInformationMessage(`👉 致爱求值预览:\n\n${stdout.trim() || '执行成功'}`);
        });
    }));

    context.subscriptions.push(vscode.languages.registerDocumentFormattingEditProvider('zhiai', {
        provideDocumentFormattingEdits(document): vscode.TextEdit[] {
            const root = vscode.workspace.workspaceFolders ? vscode.workspace.workspaceFolders[0].uri.fsPath : path.dirname(document.fileName);
            if (fs.existsSync(path.join(root, 'zhiai_fmt.py'))) {
                cp.execSync(`python zhiai_fmt.py "${document.fileName}"`, { cwd: root });
            }
            return [];
        }
    }));

    context.subscriptions.push(vscode.commands.registerCommand('zhiai.runFile', () => {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            const terminal = vscode.window.createTerminal("致爱运行");
            terminal.show();
            terminal.sendText(`python zhiai_cli.py run "${editor.document.fileName}"`);
        }
    }));

    context.subscriptions.push(vscode.debug.registerDebugAdapterDescriptorFactory('zhiai', {
        createDebugAdapterDescriptor(session): vscode.DebugAdapterDescriptor {
            return new vscode.DebugAdapterInlineImplementation(new ZhiaiDebugAdapter(session));
        }
    }));

    context.subscriptions.push(vscode.window.registerWebviewViewProvider('zhiai.zapView', new ZapWebviewProvider(context)));
}

// 🌐 DAP 调试引擎 (简版)
class ZhiaiDebugAdapter implements vscode.DebugAdapter {
    private sequence = 1;
    private _onDidSendMessage = new vscode.EventEmitter<any>();
    readonly onDidSendMessage = this._onDidSendMessage.event;
    constructor(private session: vscode.DebugSession) {}
    handleMessage(message: any): void {
        if (message.type === 'request') {
            const req = message as any;
            if (req.command === 'initialize') this.sendResponse(req, { supportsConfigurationDoneRequest: true });
            else if (req.command === 'launch') { this.sendResponse(req); this.sendEvent('stopped', { reason: 'entry', threadId: 1 }); }
            else if (req.command === 'disconnect') { this.sendResponse(req); this.sendEvent('terminated'); }
            else this.sendResponse(req);
        }
    }
    private sendResponse(request: any, body?: any): void { this._onDidSendMessage.fire({ type: 'response', seq: this.sequence++, request_seq: request.seq, command: request.command, success: true, body: body }); }
    private sendEvent(event: string, body?: any): void { this._onDidSendMessage.fire({ type: 'event', seq: this.sequence++, event: event, body: body }); }
    dispose() {}
}

class ZapWebviewProvider implements vscode.WebviewViewProvider {
    constructor(private context: vscode.ExtensionContext) {}
    resolveWebviewView(webviewView: vscode.WebviewView): void {
        webviewView.webview.options = { enableScripts: true };
        webviewView.webview.html = `
            <html><body>
            <h3>❤️ ZAP 包管理器</h3>
            <button onclick="openWiki()">📖 查看 SSA 架构文档</button>
            <script>
                const vscode = acquireVsCodeApi();
                function openWiki() { vscode.postMessage({ command: 'openWiki' }); }
            </script></body></html>`;
        webviewView.webview.onDidReceiveMessage(m => {
            if (m.command === 'openWiki') {
                const wikiPath = path.join(vscode.workspace.workspaceFolders![0].uri.fsPath, 'wiki', 'SSA_Architecture.md');
                vscode.commands.executeCommand('markdown.showPreview', vscode.Uri.file(wikiPath));
            }
        });
    }
}

export function deactivate() {}
