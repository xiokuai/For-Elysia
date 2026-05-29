# 致爱语言 寄存器虚拟机指令集架构 (ISA) 设计 (v1.1.0)

## 1. 架构概述
从 v1.1.0 开始，致爱语言将从基于栈的虚拟机（Stack-based VM）迁移到基于寄存器的虚拟机（Register-based VM）。
优势：
- 减少指令分发开销（通常指令数减少约 40-50%）。
- 直接映射局部变量到虚拟寄存器，避免频繁的 PUSH/POP。
- 更好地与 JIT 后端（3AC，三地址码）契合，大幅简化 JIT 编译器的开发和寄存器推断。

## 2. 帧结构 (Frame Structure)
每个函数调用或主程序执行将分配一个独立的调用帧（Frame）。
- **`registers`**: 一个固定大小的数组（如 256 个位置），存储当前执行上下文中的所有局部变量和临时计算结果。
- **`constants`**: 常量池的引用。
- **`env`**: 词法作用域环境引用（用于闭包和全局变量）。
- **`instructions`**: 当前指令序列。
- **`ip`**: 指令指针。

## 3. 指令集规范 (Opcode Specification)
指令编码格式保持 JSON 数组结构：`[OPCODE, arg1, arg2, ...]`。
为了提高分发速度，操作码使用字符串表示（加载时映射为整数）。
寄存器索引通常在 0 到 255 之间。

### 3.1 常量与全局变量
- `LOAD_CONST dest, const_idx`: 将 `constants[const_idx]` 的值存入 `R[dest]`。
- `LOAD_GLOBAL dest, name_idx`: 从全局/词法环境中获取名称为 `constants[name_idx]` 的变量，并存入 `R[dest]`。
- `STORE_GLOBAL name_idx, src`: 将 `R[src]` 的值存入环境中的 `constants[name_idx]`。
- `DEF_GLOBAL name_idx, src`: 在当前环境中定义新变量 `constants[name_idx]`，值为 `R[src]`。

### 3.2 寄存器移动与常量加载
- `MOVE dest, src`: 将 `R[src]` 的值复制到 `R[dest]`。
- `LOAD_NULL dest`: `R[dest] = None`
- `LOAD_BOOL dest, value`: `R[dest] = True / False` (value=1/0)

### 3.3 算术与逻辑运算
三地址码形式：`OP dest, src1, src2`
- `ADD dest, src1, src2`
- `SUB dest, src1, src2`
- `MUL dest, src1, src2`
- `DIV dest, src1, src2`
- `MOD dest, src1, src2`
- `POW dest, src1, src2`
- `EQ dest, src1, src2`
- `NEQ dest, src1, src2`
- `LT dest, src1, src2`
- `GT dest, src1, src2`
- `LTE dest, src1, src2`
- `GTE dest, src1, src2`

二地址码形式：`OP dest, src`
- `NEG dest, src`
- `NOT dest, src`

### 3.4 属性与索引
- `LOAD_INDEX dest, obj, idx`: `R[dest] = R[obj][R[idx]]`
- `STORE_INDEX obj, idx, src`: `R[obj][R[idx]] = R[src]`
- `LOAD_PROP dest, obj, name_idx`: `R[dest] = R[obj].get_prop(constants[name_idx])`
- `STORE_PROP obj, name_idx, src`: `R[obj].set_prop(constants[name_idx], R[src])`

### 3.5 控制流
- `JMP offset`: `ip = offset`
- `JMP_IF cond_reg, offset`: 如果 `R[cond_reg]` 为真，跳转到 `offset`
- `JMP_IFNOT cond_reg, offset`: 如果 `R[cond_reg]` 为假，跳转到 `offset`

### 3.6 函数调用与返回
- `CALL dest, callee_reg, arg_start, arg_count`: 调用 `R[callee_reg]`，参数从 `R[arg_start]` 连续排列，结果存入 `R[dest]`。
- `CALL_METHOD dest, obj_reg, name_idx, arg_start, arg_count`: 调用对象方法。
- `RET src`: 返回 `R[src]` 的值。
- `MAKE_FUNC dest, name_idx, arity, param_count, param_names_start, entry_ip`: 构建函数对象存入 `R[dest]`。

### 3.7 对象与数组构造
- `MAKE_ARRAY dest, item_start, count`: 创建数组。
- `MAKE_OBJECT dest, kv_start, count`: 创建对象，键值对连续排在寄存器中 (key1, val1, key2, val2...)。
- `MAKE_CLASS dest, name_idx, methods_reg`: 创建类。
- `NEW dest, klass_reg`: 实例化类。

### 3.8 错误处理与调试
- `TRY handler_ip, catch_reg`: 压入异常处理。异常发生时，异常对象存入 `R[catch_reg]`。
- `END_TRY`: 弹出异常处理。
- `RAISE src`: 抛出 `R[src]` 中的异常。
- `TRY_PROPAGATE dest, src`: 如果 `R[src]` 是失败/空则返回它，否则将解包结果存入 `R[dest]`。
- `PRINT src`: 打印 `R[src]`。
- `HALT`: 停止虚拟机。
- `BREAKPOINT`: 触发调试器。

### 3.9 异步支持
- `ASYNC_CALL dest, callee, arg_start, arg_count`
- `AWAIT dest, src`
