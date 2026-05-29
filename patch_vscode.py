import os
import json

def patch_vscode_syntax():
    f = 'vscode-zhiai/syntaxes/zhiai.tmLanguage.json'
    with open(f, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Add keywords
    control_keywords = data["repository"]["keywords"]["patterns"][0]["match"]
    control_keywords = control_keywords.replace("延迟", "延迟|异步|等待|匹配|于")
    data["repository"]["keywords"]["patterns"][0]["match"] = control_keywords

    # Add question mark operator
    operator_match = data["repository"]["operators"]["patterns"][0]["match"]
    operator_match = operator_match.replace("=", "=|\\?", 1)
    data["repository"]["operators"]["patterns"][0]["match"] = operator_match

    # Add string interpolation
    interpolation = {
        "match": "\\{[^\\}]*\\}",
        "name": "variable.other.zhiai"
    }
    data["repository"]["strings"]["patterns"][0]["patterns"].append(interpolation)
    data["repository"]["strings"]["patterns"][1]["patterns"].append(interpolation)

    with open(f, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

patch_vscode_syntax()
