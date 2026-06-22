## Context

`handler_validator.py` 原先使用 `compile()` + `exec()` 加载处理器代码，然后通过 `inspect.signature` 检查函数签名。验证阶段本应是「跑之前先检查」，但 `exec()` 将验证变成了执行，安全边界被打破。同时 `inspect.signature(run).parameters` 参数计数使用了 `{1, 3}` 的合法集，与运行时永远传单个 `HandlerContext` 的调用契约不一致。

## Goals / Non-Goals

**Goals:**
- 消除验证阶段的代码执行风险，改用 `ast.parse()` 纯静态分析
- 参数校验与 `HandlerProtocol` 对齐：严格 1 参数，覆盖全部 AST 参数槽位

**Non-Goals:**
- 不改变 `validate_handler(path: Path) -> list[str]` 对外接口
- 不改变 CLI 命令 `edera handler-validate` 的使用方式
- 不在安装时自动验证处理器（当前 `extension_manager._validate_handler_packages` 仅检查命名空间冲突）

## Decisions

### 决策 1: `ast.parse()` 替代 `exec()`

**选择**: 使用 `ast.parse(source, filename=str(path))` 纯静态分析。

**替代方案考虑**:
- `exec()` + 沙箱容器：复杂度过高，对开发工具不划算
- `ast.parse()` + 全树递归遍历：当前处理器合同要求 `run` 为模块顶层函数，浅遍历（`iter_child_nodes`）足够

**理由**: `ast.parse()` 是 Python 标准库内置，零依赖，编译阶段止步于 AST 生成（`PyCF_ONLY_AST` flag），不产出字节码，彻底消除代码执行。

### 决策 2: 参数计数覆盖全部槽位

**当前**: 仅检查 `len(fn.args.args)`。**改为**: 检查所有参数槽位之和。

`ast.arguments` 结构：
- `args` — 普通位置参数
- `posonlyargs` — positional-only（`/` 之前）
- `vararg` — `*args`
- `kwonlyargs` — keyword-only（`*` 之后）
- `kwarg` — `**kwargs`

合法条件：`len(args) + len(posonlyargs) == 1` 且 `vararg`、`kwarg`、`kwonlyargs` 均为空。

### 决策 3: 函数搜索仅检查模块顶层

`_find_function` 仅遍历 `ast.iter_child_nodes(tree)`（模块顶层语句）。这与运行时 `exec_module()` 后 `getattr(module, "run", None)` 的行为一致：嵌套在 `if`/`try`/类体内的 `run` 不会成为模块属性。

## Risks / Trade-offs

- [Risk] `ast.parse()` 对超大文件可能 OOM → **Mitigation**: 这是开发工具，输入为开发者本地文件，不在 untrusted 路径上
- [Risk] Python 3.12.3 存在 f-string 嵌套解析的 CVE-2024-4032，极端嵌套可能导致解析时间膨胀 → **Mitigation**: Python 3.12.4 已修复，项目升级即可消除
- [Trade-off] 浅遍历拒绝嵌套在 `if True: async def run(...)` 中的 handler → 这是正确的行为：此类函数不会成为模块属性，运行时也无法加载
