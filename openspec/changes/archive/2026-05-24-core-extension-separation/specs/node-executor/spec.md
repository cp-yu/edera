## MODIFIED Requirements

### Requirement: Skill 加载

Node executor SHALL 统一所有节点为 function node 执行路径：通过 importlib 从扩展 registry 加载 handler 模块，调用其 `run(ctx: HandlerContext)` 函数。MUST NOT 区分 function/llm 类型，MUST NOT 内置 pi CLI 调用逻辑。

#### Scenario: 加载扩展 handler

- **WHEN** DAG Runner 调度执行节点实例，其类型在 handler registry 中注册为 `fetch-rss`
- **THEN** executor 通过 importlib 加载对应模块，构造 `HandlerContext`，调用 `run(ctx)` 函数

#### Scenario: Handler 不在 registry 中

- **WHEN** 节点类型引用的 handler 名不在 registry 中
- **THEN** executor SHALL 返回 `NodeOutput(ok=False, error="handler not registered: <name>")`

#### Scenario: Handler 运行时异常

- **WHEN** handler `run(ctx)` 抛出异常
- **THEN** executor SHALL 捕获异常，返回 `NodeOutput(ok=False, error=异常信息)`

### Requirement: Agent 调用

Node executor SHALL 统一调用协议为 `async def run(ctx: HandlerContext) -> Any`。核心 MUST NOT 包含 pi CLI 调用、workspace 准备或 LLM 相关逻辑。LLM 调用由扩展 handler 内部通过 `_lib/` 自行实现。

#### Scenario: 统一调用协议

- **WHEN** executor 执行任意节点
- **THEN** executor SHALL 构造 `HandlerContext` 并调用 `handler.run(ctx)`，不检查 handler 内部实现方式

#### Scenario: 超时控制

- **WHEN** handler 执行时间超过 `NodeTypeDescriptor.timeout_seconds`
- **THEN** executor SHALL 取消执行并返回超时错误

### Requirement: Dynamic handler loading

系统 SHALL 通过 `importlib.util.spec_from_file_location` 从 handler registry 记录的文件路径加载 handler 模块。MUST NOT 使用 `exec()` 加载。

#### Scenario: importlib 加载 handler

- **WHEN** executor 需要执行 handler `fetch-rss`，registry 记录路径为 `extensions/rss-fetcher/handler.py`
- **THEN** executor SHALL 通过 `importlib.util.spec_from_file_location` 加载该模块，取 `run` 属性

#### Scenario: 模块缓存

- **WHEN** 同一 handler 在同一 DAG run 中被多次调用
- **THEN** executor SHALL 复用已加载的模块实例，不重复加载文件

#### Scenario: Handler 文件语法错误

- **WHEN** handler 文件包含 Python 语法错误
- **THEN** executor SHALL 捕获 `SyntaxError`，返回 `NodeOutput(ok=False, error=...)` 并记录文件路径

### Requirement: Node 作为 Entity 执行

Node executor SHALL 从 Entity Store 加载 Node Entity，根据 handler registry 查找执行入口。MUST NOT 依赖 Entity attributes 中的 `type: function/llm` 区分。

#### Scenario: 加载 Node Entity 并执行

- **WHEN** DAG Runner 调度执行一个 Node Entity
- **THEN** executor 从 Entity Store 读取该 Entity 的 attributes，提取 `handler` 字段，从 registry 查找执行入口

#### Scenario: Node Entity 无 handler 且不在 registry

- **WHEN** executor 尝试执行一个 attributes 中无 `handler` 的 Entity，且其类型不在 handler registry 中
- **THEN** executor 返回错误 "Entity is not executable: no registered handler"

## REMOVED Requirements

### Requirement: Agent Workspace 部署

**Reason**: LLM workspace 准备逻辑（`_prepare_workspace`、`_run_pi`）移出核心，由扩展 `_lib/llm.py` 承担。核心不再知道 pi CLI 的存在。

**Migration**: 原 LLM 节点（如 reader）改为 function handler 扩展，handler 内部调用 `_lib/llm.py` 完成 workspace 准备和 pi 调用。

### Requirement: pi CLI 调用规范

**Reason**: pi CLI 调用细节属于扩展实现，非核心引擎职责。

**Migration**: 调用规范文档移至 `extensions/_lib/llm.py` 模块注释。

### Requirement: Handler 每次 run 重新加载

**Reason**: 改为 importlib 模块缓存机制。同一 DAG run 内复用模块，跨 run 通过 registry 重建实现刷新。

**Migration**: 核心在每次 DAG run 开始时可选择性清除模块缓存（通过 `importlib.invalidate_caches()`）。
