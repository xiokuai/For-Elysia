# 致爱编程语言 — Bug 分析报告

> 分析日期: 2026-05-17
> 涵盖版本: v1.0.7 (Elysia Edition)
> 分析范围: `zhiai/` 核心模块 (lexer, parser, interpreter, vm, vm_jit, jit, builtins, gc, shapes)

---

## 严重程度说明

| 标记 | 含义 |
|------|------|
| 🔴 严重 | 会导致崩溃、错误结果或安全问题 |
| 🟡 中等 | 特定场景下触发异常或行为不符预期 |
| 🟢 低 | 代码质量、边缘情况或小问题 |

---

## 🔴 Bug #1: `vm.py:_op_BINOP` 缺少除零检查和字符串拼接

**文件**: `zhiai/vm.py` 第 615-621 行

**描述**: `_op_BINOP` 指令没有检查除以零，也没有处理字符串拼接（`+` 对字符串），而同文件的 `_op_ADD` 和 `_op_DIV` 正确处理了这两种情况。

**当前代码**:

```python
def _op_BINOP(self, instr):
    op = instr[1]
    b, a = self.pop(), self.pop()
    if op == '+': self.push(a + b)       # 缺少字符串拼接逻辑
    elif op == '-': self.push(a - b)
    elif op == '*': self.push(a * b)
    elif op == '/': self.push(a / b)     # 缺少除零检查
```

**影响**:
- `/` 运算符在除以零时抛出 Python 原生 `ZeroDivisionError`，而非友好的 `VMError`，错误信息不可控
- `+` 运算符在操作数为字符串时不会走 `to_str` 路径，可能产生意外行为

**修复建议**:

```python
def _op_BINOP(self, instr):
    op = instr[1]
    b, a = self.pop(), self.pop()
    if op == '+':
        if isinstance(a, str) or isinstance(b, str):
            self.push(self.to_str(a) + self.to_str(b))
        else:
            self.push(a + b)
    elif op == '-': self.push(a - b)
    elif op == '*': self.push(a * b)
    elif op == '/':
        if b == 0:
            raise VMError("除以零")
        if isinstance(a, int) and isinstance(b, int) and a % b == 0:
            self.push(a // b)
        else:
            self.push(a / b)
```

---

## 🔴 Bug #2: `vm_jit.py` — JIT 编译代码与运行时类型不匹配

**文件**: `zhiai/vm_jit.py` 第 154-169 行, 第 170-186 行

**描述**: JIT 编译器在处理 `LOAD_PROP` 和 `STORE_PROP` 时，假设 `obj.fields` 是列表（用整数索引访问 `obj.fields[offset]`），但解释器的 `Instance` 类使用字典存储字段（`self.fields = {}`）。当 JIT 编译的代码处理来自解释器路径创建的实例时，`obj.fields[offset]` 会抛出 `TypeError`，因为 dict 不支持整数索引。

同样，JIT 假设 `obj.klass['methods']` 是字典访问，但解释器的 `Class` 对象不是字典。

**当前代码 (LOAD_PROP)**:

```python
# vm_jit.py:159-164
code.append("            elif hasattr(obj, 'fields') and hasattr(obj, 'shape'):")
code.append("                offset = obj.shape.get_offset(name)")
code.append("                if offset is not None:")
code.append("                    stack.append(obj.fields[offset])")  # fields 可能是 dict
code.append("                elif name in obj.klass['methods']:")   # klass 可能不是 dict
```

**影响**: JIT 编译的函数在处理类实例属性访问时可能崩溃，导致 JIT 回退到解释器或产生错误结果。

**修复建议**: JIT 代码应检查 `fields` 的类型，或统一使用 `Instance.get_prop()` / `Instance.set_prop()` 方法。

---

## 🔴 Bug #3: `builtins.py:_网络发送` — `content_type` 参数名错误

**文件**: `zhiai/builtins.py` 第 451 行

**描述**: `_网络发送` 函数使用 `content_type='application/json'` 作为 `urllib.request.Request` 的参数，但 `Request` 构造函数没有 `content_type` 参数。该参数会被静默忽略（Python 不会报错，因为 `Request.__init__` 接受 `**kwargs`），导致 Content-Type 头未被设置，POST 请求可能被服务器拒绝。

**当前代码**:

```python
def _网络发送(url, data_dict):
    data = _json.dumps(data_dict).encode('utf-8')
    req = _urllib.Request(str(url), data=data, content_type='application/json')
    # content_type 不是 Request 的有效参数，会被忽略
```

**影响**: 所有使用 `网络发送()` 的 POST 请求都不会携带 `Content-Type: application/json` 头，导致许多 API 服务器拒绝请求或解析失败。

**修复建议**:

```python
def _网络发送(url, data_dict):
    data = _json.dumps(data_dict).encode('utf-8')
    req = _urllib.Request(str(url), data=data, headers={'Content-Type': 'application/json'})
    with _urllib.urlopen(req) as response:
        return response.read().decode('utf-8')
```

---

## 🟡 Bug #4: `vm.py:to_str` — 对 `float('inf')` 和 `float('nan')` 崩溃

**文件**: `zhiai/vm.py` 第 477-479 行, `zhiai/interpreter.py` 第 728-730 行, `zhiai/builtins.py` 第 278-280 行

**描述**: `to_str` 方法在处理浮点数时检查 `value == int(value)`，但 `float('inf')`、`float('-inf')` 和 `float('nan')` 调用 `int()` 会分别抛出 `OverflowError` 和 `ValueError`。

**受影响的代码** (三处相同模式):

```python
# vm.py:477-479
if isinstance(value, float):
    if value == int(value):  # float('inf') -> OverflowError, float('nan') -> ValueError
        return str(int(value))
```

**触发条件**: 任何产生无穷大或 NaN 的数学运算（如 `1.0 / 0.0` 如果绕过了除零检查，或 `平方根(-1)` 等）。

**修复建议** (三处都需要修改):

```python
if isinstance(value, float):
    if value != value:  # NaN check
        return "NaN"
    if value == float('inf'):
        return "Infinity"
    if value == float('-inf'):
        return "-Infinity"
    if value == int(value):
        return str(int(value))
```

---

## 🟡 Bug #5: `vm.py:_op_LOAD_INDEX` — 缺少边界检查

**文件**: `zhiai/vm.py` 第 623-639 行

**描述**: `_op_LOAD_INDEX` 对 list 和 string 的索引访问没有做上界检查（`index >= len(obj)`），越界时会抛出 Python 原生 `IndexError`，而非友好的 `VMError`。

**当前代码**:

```python
if isinstance(obj, list):
    idx = int(index)
    if idx < 0:
        idx += len(obj)
    self.push(obj[idx])  # 如果 idx >= len(obj)，抛出 Python IndexError
```

**影响**: 数组/字符串越界访问时，用户看到的是 Python 内部错误而非致爱的错误提示。

**修复建议**:

```python
if isinstance(obj, list):
    idx = int(index)
    if idx < 0:
        idx += len(obj)
    if idx < 0 or idx >= len(obj):
        raise VMError(f"索引越界: {idx} (数组长度: {len(obj)})")
    self.push(obj[idx])
```

---

## 🟡 Bug #6: `interpreter.py:ForStmt` — 循环变量使用 `define` 可能覆盖常量

**文件**: `zhiai/interpreter.py` 第 275-301 行

**描述**: `ForStmt` 的循环体中使用 `env.define(stmt.var_name, i)` 在每次迭代中定义循环变量。`define` 方法直接覆盖 `vars` 字典中的值，不检查 `consts` 集合。如果循环变量名恰好与已定义的常量同名，常量会被静默覆盖，违反了常量不可变的语义。

**当前代码**:

```python
# interpreter.py:282
while i <= end:
    env.define(stmt.var_name, i)  # 不检查是否为常量
    ...
```

**影响**: 常量保护可能被意外绕过。

**修复建议**: 首次迭代使用 `define`，后续迭代使用 `set`（会检查常量）:

```python
first = True
while i <= end:
    if first:
        env.define(stmt.var_name, i)
        first = False
    else:
        env.set(stmt.var_name, i)
    ...
```

---

## 🟡 Bug #7: `vm_jit.py` — JIT 编译的 BINOP/DIV/LOAD_LOCAL 缺少安全检查

**文件**: `zhiai/vm_jit.py` 多处

**描述**: JIT 编译器生成的代码缺少多种安全检查:

1. **BINOP (line 95-118)**: `DIV` 操作没有除零检查
2. **LOAD_LOCAL (line 43-44)**: 没有索引边界检查
3. **ADD (line 55-58)**: 没有字符串拼接逻辑

**当前代码**:

```python
# DIV — 无除零检查
elif op_name == "DIV":
    code.append("            b = stack.pop(); a = stack.pop()")
    code.append("            stack.append(a / b)")  # 除零会抛 Python 异常

# LOAD_LOCAL — 无边界检查
elif op_name == "LOAD_LOCAL":
    code.append(f"            stack.append(locals_[{instr[1]}])")  # 索引越界会抛 Python 异常
```

**影响**: JIT 编译的代码在异常情况下抛出 Python 原生异常而非致爱的错误，可能绕过致爱的 try/catch 机制。

---

## 🟢 Bug #8: `jit.py:visit_UnaryOp` — `NOT` 操作符映射错误

**文件**: `zhiai/jit.py` 第 169-172 行

**描述**: `visit_UnaryOp` 的操作符映射表使用 `"NOT"` 作为键，但致爱的非操作符在 AST 中是 `"非"` 或 `"!"`，不是 `"NOT"`。这意味着 `非 值` 在 JIT 转译模式下不会被正确转译为 Python 的 `not`。

**当前代码**:

```python
def visit_UnaryOp(self, node):
    op_map = {"-": "-", "NOT": "not "}  # "NOT" 不匹配致爱的 "非" 或 "!"
    op = op_map.get(node.op, node.op)
    return f"({op}{self.visit(node.operand)})"
```

**影响**: 使用 `非` 或 `!` 操作符的表达式在 `--jit` 模式下会生成无效的 Python 代码。

**修复建议**:

```python
op_map = {"-": "-", "非": "not ", "!": "not "}
```

---

## 🟢 Bug #9: `vm.py:_op_LOAD_PROP` — PIC 缓存的 MEGA 状态未实现

**文件**: `zhiai/vm.py` 第 653-698 行

**描述**: `_op_LOAD_PROP` 中的 Polymorphic Inline Cache (PIC) 实现了 MONO 和 POLY 状态，当缓存条目超过 4 个时标记为 `'MEGA'` (line 691)，但没有实现 MEGA 状态的处理逻辑。一旦进入 MEGA 状态，缓存检查代码会 fall through 到慢速路径，但不会执行任何 MEGA 特定的优化（如禁用缓存或切换到哈希表查找）。

**当前代码**:

```python
elif instr[2] == 'POLY':
    cache_list = instr[3]
    if len(cache_list) < 4:
        cache_list.append((obj.shape, offset))
    else:
        instr[2] = 'MEGA'  # 设置为 MEGA，但没有对应的处理分支
```

**影响**: MEGA 状态下每次属性访问都走慢速路径，性能退化。功能上不影响正确性。

---

## 🟢 Bug #10: `vm.py:_op_NEW` — 构造函数调用是空操作

**文件**: `zhiai/vm.py` 第 944-953 行

**描述**: `_op_NEW` 指令创建实例后检查是否有构造函数，但只是 `pass`，没有实际调用构造函数。注释说"构造函数处理在 `_op_CALL` 中完整实现"，但如果编译器生成 `NEW` 指令而非 `CALL` 来实例化类，构造函数不会被调用。

**当前代码**:

```python
def _op_NEW(self, instr):
    klass = self.pop()
    instance = Instance(klass)
    self.gc.track(instance)
    self.push(instance)
    if "构造" in klass["methods"]:
        constructor = klass["methods"]["构造"]
        pass  # 占位符，未实现
```

**影响**: 如果字节码使用 `NEW` 而非 `CALL` 来实例化类，构造函数不会执行，实例字段不会被初始化。

---

## 🟢 Bug #11: `vm.py:_op_STORE_INDEX` — 缺少类型检查和边界检查

**文件**: `zhiai/vm.py` 第 641-651 行

**描述**: `_op_STORE_INDEX` 对 list 的索引赋值没有检查索引是否越界，也没有检查索引是否为整数。负索引也不会被转换为正索引（与 `_op_LOAD_INDEX` 不一致）。

**当前代码**:

```python
def _op_STORE_INDEX(self, instr):
    index = self.pop()
    obj = self.pop()
    value = self.pop()
    if isinstance(obj, list):
        obj[int(index)] = value  # 无边界检查，负索引行为不一致
```

**影响**: 索引赋值越界时抛出 Python 原生 `IndexError`。

---

## 🟢 Bug #12: `jit.py:visit_AnonymousFunc` — 对多行匿名函数生成无效代码

**文件**: `zhiai/jit.py` 第 241-250 行

**描述**: `visit_AnonymousFunc` 在处理多行匿名函数体时，只检查 `len(node.body)==1 and isinstance(node.body[0], za_ast.ReturnStmt)`，如果不是单行返回，则生成 `lambda ...: None`，丢弃了函数体。

**当前代码**:

```python
return f"(lambda {', '.join(node.params)}: {self.visit(node.body[0].expr) if len(node.body)==1 and isinstance(node.body[0], za_ast.ReturnStmt) else 'None'})"
```

**影响**: 多行匿名函数在 JIT 模式下总是返回 `None`。

---

## 🟢 Bug #13: `builtins.py:_命令行参数` — 参数解析逻辑脆弱

**文件**: `zhiai/builtins.py` 第 701-709 行

**描述**: `_命令行参数` 函数的参数解析逻辑基于硬编码的子命令名和文件扩展名检查，如果用户以非标准方式调用（如 `python script.za arg1 arg2`），参数可能被错误截断。

**当前代码**:

```python
def _命令行参数():
    if len(_sys.argv) >= 2 and _sys.argv[1] in ("compile", "run", "exec"):
        return _sys.argv[2:]
    for i, arg in enumerate(_sys.argv):
        if arg.endswith(".za") or arg.endswith(".zab"):
            if "main.za" in arg or "compiler" in arg:
                return _sys.argv[i+1:]
    return _sys.argv[2:]
```

**影响**: 某些调用方式下，`命令行参数()` 返回的参数列表可能不正确。

---

## 附录: 修改文件汇总

| 文件 | Bug 编号 | 修改优先级 |
|------|----------|-----------|
| `zhiai/vm.py` | #1, #4, #5, #9, #10, #11 | 高 |
| `zhiai/vm_jit.py` | #2, #7 | 高 |
| `zhiai/builtins.py` | #3, #4, #13 | 高 |
| `zhiai/interpreter.py` | #4, #6 | 中 |
| `zhiai/jit.py` | #8, #12 | 低 |
