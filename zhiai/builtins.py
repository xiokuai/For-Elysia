"""致爱内置函数和方法"""

import random as _random
import math as _math
import os as _os
import sys as _sys
import urllib.request as _urllib
import json as _json
import tkinter as _tk
from tkinter import messagebox as _mb
from tkinter import simpledialog as _sd
import datetime as _datetime
import concurrent.futures as _futures
import threading as _threading


class ZhiAiError(Exception):
    """致爱自定义错误"""
    pass


class Option:
    """空安全保护类型 (Option)"""
    def __init__(self, value, has_value):
        self._value = value
        self._has_value = has_value

    def 是空(self):
        return not self._has_value

    def 是有(self):
        return self._has_value

    def 获取(self):
        if not self._has_value:
            raise ZhiAiError("空值安全异常: 尝试在空值(Option.空值)上调用获取()方法")
        return self._value

    def 取值(self):
        return self.获取()

    def 获取默认(self, default_val):
        return self._value if self._has_value else default_val

    def 映射(self, callback):
        if not self._has_value:
            return Option(None, False)
        wrapped = wrap_callable(callback)
        res = wrapped(self._value)
        return Option(res, True)

    def __repr__(self):
        return f"空安全.有值({repr(self._value)})" if self._has_value else "空安全.空值()"


class Result:
    """运行结果类型 (Result)"""
    def __init__(self, data, error, is_ok):
        self._data = data
        self._error = error
        self._is_ok = is_ok

    def 是成功(self):
        return self._is_ok

    def 是失败(self):
        return not self._is_ok

    def 获取(self):
        if not self._is_ok:
            raise ZhiAiError(f"运行结果异常: 尝试在失败(Result.失败)上调用获取()方法, 内部错误: {self._error}")
        return self._data

    def 取值(self):
        return self.获取()

    def 获取错误(self):
        return self._error

    def 映射(self, callback):
        if not self._is_ok:
            return Result(None, self._error, False)
        wrapped = wrap_callable(callback)
        res = wrapped(self._data)
        return Result(res, None, True)

    def __repr__(self):
        return f"运行结果.成功({repr(self._data)})" if self._is_ok else f"运行结果.失败({repr(self._error)})"


def _有值(val):
    return Option(val, True)

def _空值():
    return Option(None, False)

def _成功(data):
    return Result(data, None, True)

def _失败(err):
    return Result(None, err, False)


def _延迟(callback):
    """注册延迟执行函数"""
    global CURRENT_VM
    if CURRENT_VM:
        if CURRENT_VM.call_stack:
            CURRENT_VM.call_stack[-1].deferred.append(callback)
        else:
            CURRENT_VM.deferred.append(callback)
    return None


# ── 向量 SIMD 加速器 与 并行原语 ──────────────────────────────────────
try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

class Vector:
    """数据级 SIMD 并行向量"""
    def __init__(self, elements):
        if not isinstance(elements, list):
            raise ZhiAiError("向量初始化：参数必须是数组列表")
        self._data = [float(x) for x in elements]
        
    def 加(self, other):
        if not isinstance(other, Vector):
            raise ZhiAiError("向量加法：参数必须是另一个向量")
        if len(self._data) != len(other._data):
            raise ZhiAiError("向量加法：维度不匹配")
        if _HAS_NUMPY:
            res = _np.array(self._data) + _np.array(other._data)
            return Vector(res.tolist())
        else:
            return Vector([a + b for a, b in zip(self._data, other._data)])
            
    def 减(self, other):
        if not isinstance(other, Vector):
            raise ZhiAiError("向量减法：参数必须是另一个向量")
        if len(self._data) != len(other._data):
            raise ZhiAiError("向量减法：维度不匹配")
        if _HAS_NUMPY:
            res = _np.array(self._data) - _np.array(other._data)
            return Vector(res.tolist())
        else:
            return Vector([a - b for a, b in zip(self._data, other._data)])
            
    def 乘(self, val):
        if isinstance(val, (int, float)):
            if _HAS_NUMPY:
                res = _np.array(self._data) * val
                return Vector(res.tolist())
            else:
                return Vector([x * val for x in self._data])
        elif isinstance(val, Vector):
            if len(self._data) != len(val._data):
                raise ZhiAiError("向量乘法：维度不匹配")
            if _HAS_NUMPY:
                res = _np.array(self._data) * _np.array(val._data)
                return Vector(res.tolist())
            else:
                return Vector([a * b for a, b in zip(self._data, val._data)])
        else:
            raise ZhiAiError("向量乘法：不支持的操作数类型")
            
    def 点积(self, other):
        if not isinstance(other, Vector):
            raise ZhiAiError("向量点积：参数必须是另一个向量")
        if len(self._data) != len(other._data):
            raise ZhiAiError("向量点积：维度不匹配")
        if _HAS_NUMPY:
            return float(_np.dot(self._data, other._data))
        else:
            return sum(a * b for a, b in zip(self._data, other._data))
            
    def 列表(self):
        return list(self._data)
        
    def __repr__(self):
        return f"向量({repr(self._data)})"

def _向量(elements):
    return Vector(elements)

class AsyncTask:
    """异步任务 Future 句柄"""
    def __init__(self, future):
        self._future = future
        
    def 获取(self):
        return self._future.result()
        
    def 取值(self):
        return self.获取()
        
    def 是完成(self):
        return self._future.done()
        
    def __repr__(self):
        return f"异步任务(是否完成={self.是完成()})"

def _异步(func, *args):
    """启动一个异步线程任务"""
    wrapped = wrap_callable(func)
    executor = _futures.ThreadPoolExecutor(max_workers=1)
    fut = executor.submit(wrapped, *args)
    return AsyncTask(fut)

def _并行映射(func, arr):
    """多核并行映射 (Parallel Map)"""
    if not isinstance(arr, list):
        raise ZhiAiError("并行映射：第二个参数必须是数组")
    wrapped = wrap_callable(func)
    with _futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(wrapped, arr))
    return results


# ── 内置函数 ──────────────────────────────────────────────────────────

def _输出(*args):
    """输出内容到控制台"""
    print(*args)


def _输入(prompt=""):
    """读取用户输入"""
    return input(prompt)


def _长度(value):
    """获取长度"""
    if isinstance(value, (list, str, dict)):
        return len(value)
    raise RuntimeError(f"类型错误: 无法获取 {type(value).__name__} 的长度")


def _类型(value):
    """获取类型名称"""
    if value is None:
        return "空"
    if isinstance(value, bool):
        return "布尔"
    if isinstance(value, int):
        return "整数"
    if isinstance(value, float):
        return "浮点数"
    if isinstance(value, str):
        return "文字"
    if isinstance(value, list):
        return "数组"
    if isinstance(value, dict):
        return "对象"
    if callable(value):
        return "函数"
    return "未知"


def _转换数字(value):
    """转换为数字"""
    try:
        s = str(value).strip()
        return float(s)
    except (ValueError, TypeError):
        raise RuntimeError(f"无法将 '{value}' 转换为数字")


def _转换文字(value):
    """转换为字符串"""
    if value is None:
        return "空"
    if isinstance(value, bool):
        return "真" if value else "假"
    if isinstance(value, float):
        if value != value:
            return "NaN"
        if value == float('inf'):
            return "Infinity"
        if value == float('-inf'):
            return "-Infinity"
        if value == int(value):
            return str(int(value))
    return str(value)


def _随机数(min_val, max_val):
    """生成随机整数"""
    return _random.randint(int(min_val), int(max_val))


def _绝对值(x):
    return abs(x)


def _平方根(x):
    return _math.sqrt(x)


def _四舍五入(x, n=0):
    return round(x, int(n))


def _最大值(*args):
    if len(args) == 1 and isinstance(args[0], list):
        return max(args[0])
    return max(args)


def _最小值(*args):
    if len(args) == 1 and isinstance(args[0], list):
        return min(args[0])
    return min(args)


def _求和(arr):
    if isinstance(arr, list):
        return sum(arr)
    raise RuntimeError("求和需要一个数组")


def _范围(start, end=None, step=1):
    """生成数字范围"""
    if end is None:
        end = start
        start = 0
    return list(range(int(start), int(end), int(step)))


def _包含(collection, item):
    """检查是否包含"""
    if isinstance(collection, (list, str)):
        return item in collection
    if isinstance(collection, dict):
        return item in collection
    raise RuntimeError(f"类型错误: 无法检查包含关系")


def _是数字(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _是文字(value):
    return isinstance(value, str)


def _是数组(value):
    return isinstance(value, list)


def _是对象(value):
    return isinstance(value, dict)


def _是布尔(value):
    return isinstance(value, bool)


def _是空(value):
    return value is None


# ── 文件I/O ──────────────────────────────────────────────────────────

def _读文件(path):
    """读取文件全部内容"""
    try:
        with open(str(path), "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise RuntimeError(f"文件不存在: '{path}'")
    except Exception as e:
        raise RuntimeError(f"读取文件失败: {e}")


def _写文件(path, content):
    """写入文本到文件（如果目标是 .zab 字节码且内容为 JSON，则自动序列化为二进制 marshal 格式）"""
    try:
        path_str = str(path)
        if path_str.endswith(".zab") and isinstance(content, str):
            try:
                import json
                data = json.loads(content)
                if isinstance(data, dict) and ("constants" in data or "instructions" in data):
                    import marshal
                    with open(path_str, "wb") as f:
                        f.write(b"ZAB\x00")
                        marshal.dump(data, f)
                    return
            except Exception:
                pass
                
        with open(path_str, "w", encoding="utf-8") as f:
            f.write(str(content))
    except Exception as e:
        raise RuntimeError(f"写入文件失败: {e}")


def _追加文件(path, content):
    """追加文本到文件"""
    try:
        with open(str(path), "a", encoding="utf-8") as f:
            f.write(str(content))
    except Exception as e:
        raise RuntimeError(f"追加文件失败: {e}")


def _文件存在(path):
    """检查文件是否存在"""
    return _os.path.exists(str(path))


# ── 字符操作 ──────────────────────────────────────────────────────────

def _字符码(ch):
    """获取字符的Unicode码点"""
    s = str(ch)
    if len(s) != 1:
        raise RuntimeError(f"字符码需要单个字符，但得到 '{s}'")
    return ord(s)


def _从字符码(code):
    """从Unicode码点生成字符"""
    return chr(int(code))


# ── 错误与控制 ────────────────────────────────────────────────────────

def _错误(message):
    """抛出自定义错误"""
    raise ZhiAiError(str(message))


def _退出(code=0):
    """以退出码终止程序"""
    _sys.exit(int(code))


# ── 网络操作 ──────────────────────────────────────────────────────────

def _网络获取(url):
    """发送 GET 请求并返回响应文本"""
    try:
        with _urllib.urlopen(str(url)) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        raise RuntimeError(f"网络获取失败: {e}")

def _网络发送(url, data_dict):
    """发送 POST 请求（JSON 格式）"""
    try:
        data = _json.dumps(data_dict).encode('utf-8')
        req = _urllib.Request(str(url), data=data, headers={'Content-Type': 'application/json'})
        with _urllib.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        raise RuntimeError(f"网络发送失败: {e}")


# ── 图形界面 ──────────────────────────────────────────────────────────

def _对话框(message, title="致爱"):
    """显示一个简单的消息对话框"""
    if _os.environ.get("ZHIAI_HEADLESS") == "1":
        print(f"[对话框] {title}: {message}")
        return
    root = _tk.Tk()
    root.withdraw()
    _mb.showinfo(title, str(message))
    root.destroy()

def _确认框(message, title="致爱"):
    """显示一个确认对话框，返回布尔值"""
    if _os.environ.get("ZHIAI_HEADLESS") == "1":
        print(f"[确认框] {title}: {message} -> 默认: 真")
        return True
    root = _tk.Tk()
    root.withdraw()
    res = _mb.askyesno(title, str(message))
    root.destroy()
    return res

def _输入框(prompt, title="致爱"):
    """显示一个输入对话框，返回字符串"""
    if _os.environ.get("ZHIAI_HEADLESS") == "1":
        print(f"[输入框] {title}: {prompt} -> 默认: 小致")
        return "小致"
    root = _tk.Tk()
    root.withdraw()
    res = _sd.askstring(title, prompt)
    root.destroy()
    return res

def _列表选择(items, prompt="请选择", title="致爱"):
    """弹出一个列表选择框（简单模拟）"""
    if not isinstance(items, list):
        raise RuntimeError("列表选择需要一个数组")
    
    root = _tk.Tk()
    root.title(title)
    root.geometry("300x400")
    
    var = _tk.StringVar()
    _tk.Label(root, text=prompt).pack(pady=10)
    
    lb = _tk.Listbox(root)
    for i in items:
        lb.insert(_tk.END, str(i))
    lb.pack(expand=True, fill='both', padx=10)
    
    result = {"val": None}
    
    def on_select():
        sel = lb.curselection()
        if sel:
            result["val"] = items[sel[0]]
            root.destroy()
            
    _tk.Button(root, text="确定", command=on_select).pack(pady=10)
    root.mainloop()
    return result["val"]


def _创建窗口(title="致爱窗口", width=400, height=300):
    """创建一个 GUI 窗口"""
    root = _tk.Tk()
    root.title(title)
    # 居中显示
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - width) / 2
    y = (sh - height) / 2
    root.geometry(f"{int(width)}x{int(height)}+{int(x)}+{int(y)}")
    return root

def _创建按钮(parent, text="按钮", row=0, col=0, callback=None, colspan=1):
    """在窗口中创建一个按钮"""
    if callback:
        callback = wrap_callable(callback)
    btn = _tk.Button(parent, text=text, command=callback, font=("微软雅黑", 12))
    btn.grid(row=int(row), column=int(col), columnspan=int(colspan), sticky="nsew", padx=2, pady=2)
    # 让行列可伸缩
    parent.grid_rowconfigure(int(row), weight=1)
    parent.grid_columnconfigure(int(col), weight=1)
    return btn

def _创建文本框(parent, row=0, col=0, colspan=1):
    """在窗口中创建一个文本输入框"""
    entry = _tk.Entry(parent, font=("Arial", 20), justify="right", bd=5)
    entry.grid(row=int(row), column=int(col), columnspan=int(colspan), sticky="nsew", padx=5, pady=10)
    return entry

def _设置文本(widget, text):
    """设置控件的显示文本"""
    if hasattr(widget, "delete"):
        widget.delete(0, _tk.END)
        widget.insert(0, str(text))
    elif hasattr(widget, "config"):
        widget.config(text=str(text))

def _获取文本(widget):
    """获取控件当前的文本内容"""
    if hasattr(widget, "get"):
        return widget.get()
    elif hasattr(widget, "cget"):
        return widget.cget("text")
    return ""

def _进入主循环(root):
    """启动 GUI 事件循环"""
    root.mainloop()


# ── 对象操作 ──────────────────────────────────────────────────────────

def _对象键(obj):
    """获取对象所有键名"""
    if isinstance(obj, dict):
        return list(obj.keys())
    raise RuntimeError(f"对象键需要一个对象，但得到 {type(obj).__name__}")


def _对象值(obj):
    """获取对象所有值"""
    if isinstance(obj, dict):
        return list(obj.values())
    raise RuntimeError(f"对象值需要一个对象，但得到 {type(obj).__name__}")


def _对象合并(target, source):
    """合并两个对象"""
    if not isinstance(target, dict) or not isinstance(source, dict):
        raise RuntimeError("对象合并需要两个对象")
    result = dict(target)
    result.update(source)
    return result


def _对象有键(obj, key):
    """检查对象是否有某个键"""
    if isinstance(obj, dict):
        return key in obj
    raise RuntimeError(f"对象有键需要一个对象")


# ── 数学与格式化 ──────────────────────────────────────────────────────

def _整除(a, b):
    """整数除法"""
    if b == 0:
        raise RuntimeError("除以零")
    return int(a) // int(b)


def _格式化(template, *args):
    """格式化字符串，用 {} 作为占位符"""
    return template.format(*args)

def _时间():
    """获取当前时间戳"""
    return _datetime.datetime.now().timestamp()

def _格式化时间(timestamp, fmt="%Y-%m-%d %H:%M:%S"):
    """格式化时间戳"""
    dt = _datetime.datetime.fromtimestamp(float(timestamp))
    return dt.strftime(fmt)

def _解析JSON(text):
    """解析 JSON 字符串为对象/数组"""
    return _json.loads(text)

def _生成JSON(obj):
    """将对象/数组生成 JSON 字符串"""
    return _json.dumps(obj, ensure_ascii=False)


def _连接(*args):
    """将多个值连接成字符串。连接(数组, 分隔符) 或 连接(值1, 值2, ...)"""
    if len(args) == 2 and isinstance(args[0], list):
        sep = str(args[1])
        return sep.join(_转换文字(a) for a in args[0])
    return "".join(_转换文字(a) for a in args)


# ── 数组扩展 ──────────────────────────────────────────────────────────

def _数组(*args):
    """创建数组"""
    return list(args)


def _复制数组(arr):
    """浅拷贝数组"""
    if isinstance(arr, list):
        return list(arr)
    raise RuntimeError("复制数组需要一个数组")


def _合并数组(a, b):
    """合并两个数组"""
    if isinstance(a, list) and isinstance(b, list):
        return a + b
    raise RuntimeError("合并数组需要两个数组")


def _添加(arr, item):
    """向数组添加元素"""
    if isinstance(arr, list):
        arr.append(item)
        return arr
    raise RuntimeError("添加需要一个数组")


def _删除(arr, index):
    """从数组删除元素"""
    if isinstance(arr, list):
        return arr.pop(int(index))
    raise RuntimeError("删除需要一个数组")


def _截取(value, start, end=None):
    """截取字符串或数组"""
    if end is None:
        end = len(value)
    return value[int(start):int(end)]


def _索引(arr, item):
    """查找元素索引"""
    if isinstance(arr, list):
        for i, v in enumerate(arr):
            if type(v) == type(item) and v == item:
                return i
        return -1
    if isinstance(arr, str):
        try:
            return arr.index(item)
        except ValueError:
            return -1
    return -1


def _命令行参数():
    """获取脚本的命令行参数列表"""
    # 尝试跳过致爱执行器自身的参数
    filtered = []
    skip = True
    for arg in _sys.argv:
        if not skip:
            filtered.append(arg)
        elif arg.endswith(".za") or arg.endswith(".zab"):
            skip = False
    if not filtered and len(_sys.argv) > 1:
        # 如果是 REPL 或某些特殊模式，可能没找到脚本名，回退到跳过第一个
        if _sys.argv[1] in ("run", "compile", "exec"):
             return _sys.argv[3:] if len(_sys.argv) > 2 else []
        return _sys.argv[1:]
    return filtered



# 内置函数表
BUILTINS = {
    "输出": _输出,
    "输入": _输入,
    "长度": _长度,
    "类型": _类型,
    "转换数字": _转换数字,
    "转换文字": _转换文字,
    "随机数": _随机数,
    "绝对值": _绝对值,
    "平方根": _平方根,
    "四舍五入": _四舍五入,
    "最大值": _最大值,
    "最小值": _最小值,
    "求和": _求和,
    "范围": _范围,
    "包含": _包含,
    "是数字": _是数字,
    "是文字": _是文字,
    "是数组": _是数组,
    "是对象": _是对象,
    "是布尔": _是布尔,
    "是空": _是空,
    # SIMD 与 并行计算原语
    "向量": _向量,
    "异步": _异步,
    "并行映射": _并行映射,
    # 空值安全与异常结果
    "有值": _有值,
    "空值": _空值,
    "成功": _成功,
    "失败": _失败,
    "延迟": _延迟,
    # 文件I/O
    "读文件": _读文件,
    "写文件": _写文件,
    "追加文件": _追加文件,
    "文件存在": _文件存在,
    # 字符操作
    "字符码": _字符码,
    "从字符码": _从字符码,
    # 错误与控制
    "错误": _错误,
    "退出": _退出,
    # 对象操作
    "对象键": _对象键,
    "对象值": _对象值,
    "对象合并": _对象合并,
    "对象有键": _对象有键,
    # 数学与格式化
    "整除": _整除,
    "格式化": _格式化,
    "连接": _连接,
    "时间": _时间,
    "格式化时间": _格式化时间,
    "解析JSON": _解析JSON,
    "生成JSON": _生成JSON,
    # 数组扩展
    "数组": _数组,
    "复制数组": _复制数组,
    "合并数组": _合并数组,
    "添加": _添加,
    "删除": _删除,
    "截取": _截取,
    "索引": _索引,
    # 系统
    "命令行参数": _命令行参数,
    # 网络
    "网络获取": _网络获取,
    "网络发送": _网络发送,
    # 图形界面
    "对话框": _对话框,
    "确认框": _确认框,
    "输入框": _输入框,
    "列表选择": _列表选择,
    "创建窗口": _创建窗口,
    "创建按钮": _创建按钮,
    "创建文本框": _创建文本框,
    "设置文本": _设置文本,
    "获取文本": _获取文本,
    "进入主循环": _进入主循环,
}


CURRENT_VM = None

class VMCallableWrapper:
    """可调用包装器：允许 Python 原生方法高效地回调 VM 内部的函数对象"""
    def __init__(self, func_dict):
        self.func_dict = func_dict

    def __call__(self, *args):
        global CURRENT_VM
        if CURRENT_VM is None:
            raise RuntimeError("无法回调致爱函数：当前没有活跃的虚拟机实例")
        return CURRENT_VM.call_function_nested(self.func_dict, list(args))

def wrap_callable(func):
    """如果是一个致爱函数字典，则自动包装为可调用对象；否则保持原样"""
    if isinstance(func, dict) and func.get("type") == "function":
        return VMCallableWrapper(func)
    return func


# ── 高阶函数（顶级版本，同时支持数组方法形式） ──────────────────────────

def _筛选(arr, func):
    """筛选满足条件的元素: 筛选(数组, 函数)"""
    if not isinstance(arr, list):
        if hasattr(arr, "筛选"):
            return getattr(arr, "筛选")(func)
        raise RuntimeError("筛选: 第一个参数必须是数组")
    func = wrap_callable(func)
    return [item for item in arr if func(item)]


def _映射(arr, func):
    """对每个元素执行函数: 映射(数组, 函数)"""
    if not isinstance(arr, list):
        if hasattr(arr, "映射"):
            return getattr(arr, "映射")(func)
        raise RuntimeError("映射: 第一个参数必须是数组")
    func = wrap_callable(func)
    return [func(item) for item in arr]


def _排序(arr, key_func=None):
    """排序数组（可选排序函数）: 排序(数组) 或 排序(数组, 函数)"""
    if not isinstance(arr, list):
        raise RuntimeError("排序: 第一个参数必须是数组")
    result = list(arr)
    if key_func is None:
        result.sort()
    else:
        key_func = wrap_callable(key_func)
        result.sort(key=lambda x: key_func(x))
    return result


def _归约(arr, func, initial=None):
    """归约数组: 归约(数组, 函数, 初始值)"""
    if not isinstance(arr, list):
        raise RuntimeError("归约: 第一个参数必须是数组")
    func = wrap_callable(func)
    if not arr:
        return initial
    acc = initial if initial is not None else arr[0]
    start = 0 if initial is not None else 1
    for item in arr[start:]:
        acc = func(acc, item)
    return acc


def _查找(arr, func):
    """查找第一个满足条件的元素: 查找(数组, 函数)"""
    if not isinstance(arr, list):
        raise RuntimeError("查找: 第一个参数必须是数组")
    func = wrap_callable(func)
    for item in arr:
        if func(item):
            return item
    return None


def _每个(arr, func):
    """对每个元素执行函数（不返回值）: 每个(数组, 函数)"""
    if not isinstance(arr, list):
        raise RuntimeError("每个: 第一个参数必须是数组")
    func = wrap_callable(func)
    for item in arr:
        func(item)
    return None


def _任意(arr, func):
    """是否有任意元素满足条件: 任意(数组, 函数)"""
    if not isinstance(arr, list):
        raise RuntimeError("任意: 第一个参数必须是数组")
    func = wrap_callable(func)
    return any(func(item) for item in arr)


def _全部(arr, func):
    """是否所有元素满足条件: 全部(数组, 函数)"""
    if not isinstance(arr, list):
        raise RuntimeError("全部: 第一个参数必须是数组")
    func = wrap_callable(func)
    return all(func(item) for item in arr)


BUILTINS.update({
    "筛选": _筛选,
    "映射": _映射,
    "排序": _排序,
    "归约": _归约,
    "查找": _查找,
    "每个": _每个,
    "任意": _任意,
    "全部": _全部,
})



# ── 数组方法 ──────────────────────────────────────────────────────────

def array_add(arr, item):
    arr.append(item)
    return arr


def array_remove(arr, index):
    return arr.pop(int(index))


def array_contains(arr, item):
    return item in arr


def array_sort(arr):
    arr.sort()
    return arr


def array_reverse(arr):
    arr.reverse()
    return arr


def array_join(arr, func):
    """对每个元素执行函数并返回结果数组"""
    func = wrap_callable(func)
    return [func(item) for item in arr]


def array_filter(arr, func):
    """筛选满足条件的元素"""
    func = wrap_callable(func)
    return [item for item in arr if func(item)]


def array_find(arr, func):
    """查找第一个满足条件的元素"""
    func = wrap_callable(func)
    for item in arr:
        if func(item):
            return item
    return None


def array_index(arr, item):
    """查找元素索引"""
    try:
        return arr.index(item)
    except ValueError:
        return -1


def array_slice(arr, start, end=None):
    """截取子数组"""
    if end is None:
        return arr[int(start):]
    return arr[int(start):int(end)]


ARRAY_METHODS = {
    "添加": array_add,
    "删除": array_remove,
    "包含": array_contains,
    "排序": array_sort,
    "反转": array_reverse,
    "连接": array_join,
    "筛选": array_filter,
    "查找": array_find,
    "索引": array_index,
    "截取": array_slice,
}


# ── 字符串方法 ────────────────────────────────────────────────────────

def str_split(s, sep):
    return s.split(sep)


def str_replace(s, old, new):
    return s.replace(old, new)


def str_find(s, sub):
    return s.find(sub)


def str_contains(s, sub):
    return sub in s


def str_trim(s):
    return s.strip()


def str_lower(s):
    return s.lower()


def str_upper(s):
    return s.upper()


def str_startswith(s, prefix):
    return s.startswith(prefix)


def str_endswith(s, suffix):
    return s.endswith(suffix)


def str_substr(s, start, end=None):
    if end is None:
        return s[int(start):]
    return s[int(start):int(end)]


STRING_METHODS = {
    "分割": str_split,
    "替换": str_replace,
    "查找": str_find,
    "包含": str_contains,
    "修剪": str_trim,
    "小写": str_lower,
    "大写": str_upper,
    "开头是": str_startswith,
    "结尾是": str_endswith,
    "截取": str_substr,
}

# ── 批处理映射 ──────────────────────────────────────────────────────────
# 为 BATCH_OP 指令提供快速索引

def batch_matrix_add(m1, m2):
    """二维矩阵相加"""
    if not isinstance(m1, list) or not isinstance(m2, list):
        raise RuntimeError("矩阵相加：参数必须是二维数组")
    if not m1 or not m2 or not isinstance(m1[0], list) or not isinstance(m2[0], list):
        raise RuntimeError("矩阵相加：参数必须是有效的二维数组")
    return [[m1[i][j] + m2[i][j] for j in range(len(m1[0]))] for i in range(len(m1))]


def batch_matrix_mul(m1, m2):
    """二维矩阵乘法 (点乘)"""
    if not isinstance(m1, list) or not isinstance(m2, list):
        raise RuntimeError("矩阵相乘：参数必须是二维数组")
    if not m1 or not m2 or not isinstance(m1[0], list) or not isinstance(m2[0], list):
        raise RuntimeError("矩阵相乘：参数必须是有效的二维数组")
    r1, c1 = len(m1), len(m1[0])
    r2, c2 = len(m2), len(m2[0])
    if c1 != r2:
        raise RuntimeError(f"矩阵相乘：维度不匹配 ({r1}x{c1} 与 {r2}x{c2})")
    result = [[0] * c2 for _ in range(r1)]
    for i in range(r1):
        for j in range(c2):
            val = 0
            for k in range(c1):
                val += m1[i][k] * m2[k][j]
            result[i][j] = val
    return result


def batch_matrix_transpose(m):
    """二维矩阵转置"""
    if not isinstance(m, list) or not m or not isinstance(m[0], list):
        raise RuntimeError("矩阵转置：参数必须是二维数组")
    return [list(x) for x in zip(*m)]


def batch_regex_match(pattern, text):
    """正则表达式匹配，返回所有匹配项的数组"""
    import re
    return re.findall(str(pattern), str(text))


def batch_regex_replace(pattern, repl, text):
    """正则表达式替换，返回替换后的文本"""
    import re
    return re.sub(str(pattern), str(repl), str(text))


BATCH_FUNC_MAP = {
    1: _筛选,
    2: _映射,
    3: array_sort,
    4: str_split,
    5: str_replace,
    6: batch_matrix_add,
    7: batch_matrix_mul,
    8: batch_matrix_transpose,
    9: batch_regex_match,
    10: batch_regex_replace,
}

BUILTINS.update({
    "矩阵相加": batch_matrix_add,
    "矩阵相乘": batch_matrix_mul,
    "矩阵转置": batch_matrix_transpose,
    "正则匹配": batch_regex_match,
    "正则替换": batch_regex_replace,
})
