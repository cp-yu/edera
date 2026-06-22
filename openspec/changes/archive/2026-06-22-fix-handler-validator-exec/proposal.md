## Why

`handler-validator` 使用 `exec()` 执行处理器代码进行验证，导致验证阶段即可触发任意代码执行。同时验证逻辑的参数检查不完整，漏掉了 positional-only、keyword-only、`*args`、`**kwargs` 等参数形态。

## What Changes

- 将 `exec()` 替换为 `ast.parse()` 纯静态分析，消除代码执行风险
- 参数校验从「接受 1 或 3 个参数」改为「严格 1 个参数」，匹配 `HandlerContext` 调用契约
- 新增 `async def` 检查：handler MUST 声明为 `async def run`，非 async 处理器在验证阶段即可被拒绝
- 参数计数覆盖全部参数槽位：`args` + `posonlyargs` + `kwonlyargs` + `vararg` + `kwarg`

## Capabilities

### Modified Capabilities

- `handler-context-protocol`: 新增 handler 验证规则 requirement，将验证行为从代码执行改为静态分析，并覆盖完整参数形态检查

## Impact

- 受影响的代码：`packages/core/src/edera_core/handler_validator.py`（重写）、`tests/core/unit/test_handler_validator.py`（13 个测试覆盖）
- CLI 命令 `edera handler-validate` 行为不变（接口兼容），但不再执行处理器代码
- 无破坏性变更：对外接口 `validate_handler(path: Path) -> list[str]` 签名不变
