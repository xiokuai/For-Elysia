"""致爱内置函数和方法"""

import random as _random
import math as _math
import os as _os
import sys as _sys


class ZhiAiError(Exception):
    """致爱自定义错误"""
    pass


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
        # 去掉多余的 .0
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
    """写入文本到文件"""
    try:
        with open(str(path), "w", encoding="utf-8") as f:
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
    s = str(template)
    for arg in args:
        s = s.replace("{}", _转换文字(arg), 1)
    return s


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
    """获取命令行参数（不含解释器和脚本名）"""
    return _sys.argv[2:]


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
}


# ── 高阶函数（顶级版本，同时支持数组方法形式） ──────────────────────────

def _筛选(arr, func):
    """筛选满足条件的元素: 筛选(数组, 函数)"""
    if not isinstance(arr, list):
        raise RuntimeError("筛选: 第一个参数必须是数组")
    return [item for item in arr if func(item)]


def _映射(arr, func):
    """对每个元素执行函数: 映射(数组, 函数)"""
    if not isinstance(arr, list):
        raise RuntimeError("映射: 第一个参数必须是数组")
    return [func(item) for item in arr]


def _排序(arr, key_func=None):
    """排序数组（可选排序函数）: 排序(数组) 或 排序(数组, 函数)"""
    if not isinstance(arr, list):
        raise RuntimeError("排序: 第一个参数必须是数组")
    result = list(arr)
    if key_func is None:
        result.sort()
    else:
        result.sort(key=lambda x: key_func(x))
    return result


def _归约(arr, func, initial=None):
    """归约数组: 归约(数组, 函数, 初始值)"""
    if not isinstance(arr, list):
        raise RuntimeError("归约: 第一个参数必须是数组")
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
    for item in arr:
        if func(item):
            return item
    return None


def _每个(arr, func):
    """对每个元素执行函数（不返回值）: 每个(数组, 函数)"""
    if not isinstance(arr, list):
        raise RuntimeError("每个: 第一个参数必须是数组")
    for item in arr:
        func(item)
    return None


def _任意(arr, func):
    """是否有任意元素满足条件: 任意(数组, 函数)"""
    if not isinstance(arr, list):
        raise RuntimeError("任意: 第一个参数必须是数组")
    return any(func(item) for item in arr)


def _全部(arr, func):
    """是否所有元素满足条件: 全部(数组, 函数)"""
    if not isinstance(arr, list):
        raise RuntimeError("全部: 第一个参数必须是数组")
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
    return [func(item) for item in arr]


def array_filter(arr, func):
    """筛选满足条件的元素"""
    return [item for item in arr if func(item)]


def array_find(arr, func):
    """查找第一个满足条件的元素"""
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

BATCH_FUNC_MAP = {
    1: _筛选,
    2: _映射,
    3: array_sort,
    4: str_split,
    5: str_replace,
}
