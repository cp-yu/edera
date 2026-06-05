## MODIFIED Requirements

### Requirement: Skill 加载

Node executor SHALL 统一所有节点为 function node 执行路径：通过 importlib 从 `DagExecutionSnapshot` 的 `handler_resolver` 查询 handler 元数据并加载模块，调用其 `run(ctx: HandlerContext)` 函数。MUST NOT 使用 handler registry。

#### Scenario: 加载扩展 handler

- **WHEN** DAG Runner 调度执行节点实例，其类型为 `fetch-rss`
- **THEN** executor 通过 `snapshot.handler_resolver.get("fetch-rss")` 查询 handler 元数据
- **THEN** executor 使用返回的 path 通过 importlib 加载模块
- **THEN** executor 构造 `HandlerContext`，调用 `run(ctx)` 函数

#### Scenario: Handler 不在数据库中

- **WHEN** 节点类型引用的 handler 名在数据库中不存在
- **THEN** resolver 抛出 `HandlerNotFoundError`
- **THEN** executor SHALL 返回 `NodeOutput(ok=False, error="handler not found: <name>")`

#### Scenario: Handler 运行时异常

- **WHEN** handler `run(ctx)` 抛出异常
- **THEN** executor SHALL 捕获异常，返回 `NodeOutput(ok=False, error=异常信息)`

### Requirement: Dynamic handler loading

系统 SHALL 通过 `importlib.util.spec_from_file_location` 从 `DatabaseHandlerResolver` 返回的文件路径加载 handler 模块。MUST NOT 使用 `exec()` 加载，MUST NOT 使用 handler registry。

#### Scenario: importlib 加载 handler

- **WHEN** executor 需要执行 handler `fetch-rss`
- **WHEN** resolver 返回路径 `handlers/rss-fetcher/handler.py`
- **THEN** executor SHALL 通过 `importlib.util.spec_from_file_location` 加载该模块，取 `run` 属性

#### Scenario: 模块缓存

- **WHEN** 同一 handler 在同一 DAG run 中被多次调用
- **THEN** executor SHALL 复用已加载的模块实例（存储在 `_modules` dict 中），不重复加载文件
- **THEN** executor 不再查询 resolver（module 已缓存）

#### Scenario: Handler 文件语法错误

- **WHEN** handler 文件包含 Python 语法错误
- **THEN** executor SHALL 捕获 `SyntaxError`，返回 `NodeOutput(ok=False, error=...)` 并记录文件路径

## ADDED Requirements

### Requirement: 接收执行快照

Node executor SHALL 接收 `DagExecutionSnapshot` 作为构造参数，从快照中获取 handler resolver 和 entity types，不再接收 `handler_registry` 参数。

#### Scenario: 使用快照构造 executor

- **WHEN** DagController 创建 `NodeExecutor(snapshot=snapshot, ...)`
- **THEN** executor 内部保存 `self.snapshot` 引用
- **THEN** executor 不再接收或保存 `handler_registry` 参数

#### Scenario: 从快照获取 handler resolver

- **WHEN** executor 执行 `_load_handler(handler_name)`
- **THEN** executor 调用 `self.snapshot.handler_resolver.get(handler_name)` 查询元数据
- **THEN** 使用返回的 path 加载 module

#### Scenario: 从快照获取 entity types

- **WHEN** executor 需要访问 entity type 配置
- **THEN** executor 从 `self.snapshot.entity_types` 获取（dict）
- **THEN** executor 不访问全局 `AppConfig.entity_types`
