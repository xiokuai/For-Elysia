import os
import re

def patch_builtins():
    f = 'zhiai/builtins.py'
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    # Refactor _读文件
    old_read = """def _读文件(path):
    \"\"\"读取文件全部内容\"\"\"
    try:
        with open(str(path), "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise RuntimeError(f"文件不存在: '{path}'")
    except Exception as e:
        raise RuntimeError(f"读取文件失败: {e}")"""
    new_read = """def _读文件(path):
    \"\"\"读取文件全部内容\"\"\"
    try:
        with open(str(path), "r", encoding="utf-8") as f:
            return _成功(f.read())
    except FileNotFoundError:
        return _失败(f"文件不存在: '{path}'")
    except Exception as e:
        return _失败(f"读取文件失败: {e}")"""
    content = content.replace(old_read, new_read)

    # Refactor _写文件
    old_write = """def _写文件(path, content):
    \"\"\"写入文本到文件（如果目标是 .zab 字节码且内容为 JSON，则自动序列化为二进制 marshal 格式）\"\"\"
    try:
        path_str = str(path)
        if path_str.endswith(".zab") and isinstance(content, str):
            try:
                import json
                data = json.loads(content)
                if isinstance(data, dict) and ("constants" in data or "instructions" in data):
                    import marshal
                    with open(path_str, "wb") as f:
                        f.write(b"ZAB\\x00")
                        marshal.dump(data, f)
                    return
            except Exception:
                pass
                
        with open(path_str, "w", encoding="utf-8") as f:
            f.write(str(content))
    except Exception as e:
        raise RuntimeError(f"写入文件失败: {e}")"""
    new_write = """def _写文件(path, content):
    \"\"\"写入文本到文件（如果目标是 .zab 字节码且内容为 JSON，则自动序列化为二进制 marshal 格式）\"\"\"
    try:
        path_str = str(path)
        if path_str.endswith(".zab") and isinstance(content, str):
            try:
                import json
                data = json.loads(content)
                if isinstance(data, dict) and ("constants" in data or "instructions" in data):
                    import marshal
                    with open(path_str, "wb") as f:
                        f.write(b"ZAB\\x00")
                        marshal.dump(data, f)
                    return _成功(True)
            except Exception:
                pass
                
        with open(path_str, "w", encoding="utf-8") as f:
            f.write(str(content))
        return _成功(True)
    except Exception as e:
        return _失败(f"写入文件失败: {e}")"""
    content = content.replace(old_write, new_write)

    # Refactor _追加文件
    old_append = """def _追加文件(path, content):
    \"\"\"追加文本到文件\"\"\"
    try:
        with open(str(path), "a", encoding="utf-8") as f:
            f.write(str(content))
    except Exception as e:
        raise RuntimeError(f"追加文件失败: {e}")"""
    new_append = """def _追加文件(path, content):
    \"\"\"追加文本到文件\"\"\"
    try:
        with open(str(path), "a", encoding="utf-8") as f:
            f.write(str(content))
        return _成功(True)
    except Exception as e:
        return _失败(f"追加文件失败: {e}")"""
    content = content.replace(old_append, new_append)

    # Refactor _网络获取
    old_net_get = """def _网络获取(url):
    \"\"\"发送 HTTP GET 请求 (需要 urllib.request)\"\"\"
    import urllib.request
    try:
        with urllib.request.urlopen(str(url)) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"网络获取失败: {e}")"""
    new_net_get = """def _网络获取(url):
    \"\"\"发送 HTTP GET 请求 (需要 urllib.request)\"\"\"
    import urllib.request
    try:
        with urllib.request.urlopen(str(url)) as response:
            return _成功(response.read().decode("utf-8"))
    except Exception as e:
        return _失败(f"网络获取失败: {e}")"""
    content = content.replace(old_net_get, new_net_get)

    # Refactor _网络发送
    old_net_post = """def _网络发送(url, data):
    \"\"\"发送 HTTP POST 请求\"\"\"
    import urllib.request
    import urllib.parse
    import json
    
    try:
        if isinstance(data, dict):
            req_data = json.dumps(data).encode("utf-8")
            headers = {'Content-Type': 'application/json'}
        else:
            req_data = str(data).encode("utf-8")
            headers = {'Content-Type': 'text/plain'}
            
        req = urllib.request.Request(str(url), data=req_data, headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"网络发送失败: {e}")"""
    new_net_post = """def _网络发送(url, data):
    \"\"\"发送 HTTP POST 请求\"\"\"
    import urllib.request
    import urllib.parse
    import json
    
    try:
        if isinstance(data, dict):
            req_data = json.dumps(data).encode("utf-8")
            headers = {'Content-Type': 'application/json'}
        else:
            req_data = str(data).encode("utf-8")
            headers = {'Content-Type': 'text/plain'}
            
        req = urllib.request.Request(str(url), data=req_data, headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            return _成功(response.read().decode("utf-8"))
    except Exception as e:
        return _失败(f"网络发送失败: {e}")"""
    content = content.replace(old_net_post, new_net_post)

    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

patch_builtins()

def patch_compiler():
    f = 'compiler/main.za'
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    # Update `读文件(输入文件)` to `读文件(输入文件)?` in 编译文件
    content = content.replace(
        '  让 源码 = 读文件(输入文件)\n  如果 源码 == 空 或者 源码 == "" 则\n    错误("无法读取文件: " + 输入文件)\n  结束',
        '  让 源码 = 读文件(输入文件)?\n  如果 源码 == 空 或者 源码 == "" 则\n    错误("无法读取文件: " + 输入文件)\n  结束'
    )

    # Update `写文件` to `写文件(...)` in 编译文件
    # Actually wait, `写文件` now returns a Result, but compiler doesn't check it. Let's add `?`.
    content = content.replace(
        '  写文件(输出文件, JSON输出)',
        '  写文件(输出文件, JSON输出)?'
    )

    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

patch_compiler()
