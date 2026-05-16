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

            return completionItems;
        }
    });

    context.subscriptions.push(provider);
}

export function deactivate() {}
