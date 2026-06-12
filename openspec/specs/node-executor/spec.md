---
capabilities:
  - cap.operations.node-executor
---
# node-executor Specification

## Purpose
定义 Skill 加载、Agent 调用、I/O 管理、Node 执行隔离等能力。
## Requirements
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

### Requirement: Agent 调用

Node executor SHALL 统一调用协议为 `async def run(ctx: HandlerContext) -> Any`。核心 MUST NOT 包含 pi CLI 调用、workspace 准备或 LLM 相关逻辑。LLM 调用由扩展 handler 内部通过 `_lib/` 自行实现。

#### Scenario: 统一调用协议

- **WHEN** executor 执行任意节点
- **THEN** executor SHALL 构造 `HandlerContext` 并调用 `handler.run(ctx)`，不检查 handler 内部实现方式

#### Scenario: 超时控制

- **WHEN** handler 执行时间超过 `NodeTypeDescriptor.timeout_seconds`
- **THEN** executor SHALL 取消执行并返回超时错误

### Requirement: I/O 管理
Node executor SHALL 管理节点的输入和输出，MUST 确保输入输出均为 Pydantic 模型序列化后的 JSON。

#### Scenario: 输入序列化
- **WHEN** DAG Runner 传入 Pydantic 模型实例作为节点输入
- **THEN** executor 将其序列化为 JSON 字符串传递给 Agent

#### Scenario: 输出反序列化
- **WHEN** Agent 返回 JSON 字符串输出
- **THEN** executor 将其反序列化为对应的 Pydantic 模型实例返回给 DAG Runner

### Requirement: Node 执行隔离
Node executor MUST 保证每个 Node 实例独立执行，Node 之间无直接通信。Node 不感知自身在 DAG 中的位置。

#### Scenario: 并发 Node 隔离
- **WHEN** 同一 Skill 的两个 Node 实例并发执行
- **THEN** 两个实例互不影响，各自独立完成执行并返回结果

### Requirement: Node execution by instance ID
系统 SHALL 按 DAG 拓扑顺序调度节点实例执行，使用实例 UUID 作为调度和状态上报的索引键。

#### Scenario: Schedule by instance ID
- **WHEN** DAG 执行引擎启动一个运行周期
- **THEN** 系统 SHALL 按拓扑顺序遍历节点实例（通过 UUID 标识），而非节点类型名

#### Scenario: Runtime status indexed by instance ID
- **WHEN** 节点实例执行完成并上报状态
- **THEN** 系统 SHALL 以实例 UUID 为键存储运行状态（running/succeeded/failed）

#### Scenario: Multiple instances of same type execute independently
- **WHEN** DAG 中存在同一类型的多个实例
- **THEN** 系统 SHALL 独立调度和执行每个实例，各自维护独立的运行状态

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

### Requirement: Instance config resolution
系统 SHALL 在执行节点实例时合并类型定义和实例级配置，实例配置优先。

#### Scenario: Merge type and instance config
- **WHEN** 系统准备执行一个节点实例
- **THEN** 系统 SHALL 以类型定义为基础，用实例 `config` 中的字段覆盖对应运行时参数（source_names、parameters、model、skills）

#### Scenario: Structural fields from type only
- **WHEN** 系统解析节点实例的执行配置
- **THEN** 系统 SHALL 始终从类型定义获取 `input_type`、`output_type`、`role`、`handler`、`system_prompt_file`，忽略实例级对这些字段的任何覆盖

### Requirement: Entity context injection

Node executor SHALL 在节点执行时注入实体上下文，提供 `context.get_entity()`, `context.save_entity()`, `context.create_entity()` 接口。

#### Scenario: Get entity by reference

- **WHEN** 节点调用 `context.get_entity("stock:00700.HK")`
- **THEN** executor 解析引用（UUID 或业务 ID），返回对应的实体对象

#### Scenario: Get entity not found

- **WHEN** 节点调用 `context.get_entity()` 引用不存在的实体
- **THEN** executor 抛出异常 "Entity not found: <reference>"

#### Scenario: Save entity with permission check

- **WHEN** 节点修改实体后调用 `context.save_entity(entity)`
- **THEN** executor 检查字段权限，保存允许修改的字段，记录警告日志并忽略受保护字段

#### Scenario: Create new entity

- **WHEN** 节点调用 `context.create_entity(type="stock", attributes={...})`
- **THEN** executor 生成 UUID，验证 attributes，保存到 `entities.yaml`

### Requirement: Field permission enforcement

Node executor SHALL 在节点访问实体字段时检查权限，违反权限时发出警告并阻止操作。

#### Scenario: Read protected field

- **WHEN** 节点尝试读取权限为 `none` 或 `write-only` 的字段
- **THEN** executor 记录警告 "Permission denied: <entity_type>.<field> is not readable"，返回 None

#### Scenario: Write protected field

- **WHEN** 节点尝试修改权限为 `none` 或 `read-only` 的字段
- **THEN** executor 记录警告 "Permission denied: <entity_type>.<field> is not writable"，不保存修改

#### Scenario: Permission check uses instance overrides

- **WHEN** 节点实例配置了 `entity_permissions: {stock: {code: read-write}}`
- **THEN** executor 使用实例权限（`read-write`）而非默认权限（`read-only`）

### Requirement: Entity auto-discovery

Node executor SHALL 在节点配置只指定 source 而未指定 entities 时，自动从 `entity-relations.yaml` 发现关联实体。

#### Scenario: Auto-discover entities from source

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss"}`，未指定 `entities`
- **THEN** executor 查找 `entity-relations.yaml` 中包含该 source 的关系，返回关联的其他实体

#### Scenario: Explicit entities override auto-discovery

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss", entities: ["stock:600519.SH"]}`
- **THEN** executor 使用显式配置的 `entities`，忽略自动发现

#### Scenario: Empty entities disable auto-discovery

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss", entities: []}`
- **THEN** executor 不提供任何实体上下文

### Requirement: Node 作为 Entity 执行

Node executor SHALL 从当前 DAG run 的 `DagExecutionSnapshot` 中解析 Node type 和 handler metadata。执行入口 SHALL 通过 `snapshot.handler_resolver` 获取，MUST NOT 通过 handler registry 获取。

#### Scenario: 加载 Node Entity 并执行

- **WHEN** DAG Runner 调度执行一个 Node Entity
- **THEN** executor SHALL 从当前执行上下文解析该 Node 的 type 和 handler 字段
- **AND** executor SHALL 通过 `snapshot.handler_resolver.get(<handler>)` 查询执行入口 metadata

#### Scenario: Node Entity 无 handler 且 resolver 不存在执行入口

- **WHEN** executor 尝试执行一个无法解析 handler 的 Node Entity
- **THEN** executor SHALL 返回错误 "Entity is not executable: no registered handler" 或等价的 handler-not-found 错误

### Requirement: Node 输出存储为 Entity

Node executor SHALL 将节点执行输出存储为输出型 Entity（存储在数据库层），替代当前的独立数据模型表。

#### Scenario: 存储 Node 输出为 Entity

- **WHEN** 节点执行成功产出结果
- **THEN** executor 将输出存储为一个 Entity（type 由节点的 `output_type` 决定），包含 `run_id`、`node_id`、`payload` 等 attributes

#### Scenario: 输出 Entity 可被后续节点引用

- **WHEN** 下游节点需要引用上游的输出
- **THEN** 系统通过 Entity Store 查询对应 run_id 和 node_id 的输出 Entity

### Requirement: Session ID 记录

Node executor SHALL 为 LLM 节点记录 pi session ID 到输出 Entity 的 attributes 中，支持后续 session resume。

#### Scenario: 记录 session ID

- **WHEN** LLM 节点通过 pi 执行完成
- **THEN** executor 将 session 目录路径记录到输出 Entity 的 `attributes.session_id` 字段

#### Scenario: Session ID 可查询

- **WHEN** 用户查询某次 Node 执行的 session ID
- **THEN** 系统从输出 Entity 的 attributes 中返回 `session_id` 值

### Requirement: Tools 白名单传递
Node executor SHALL 根据节点配置的 `tools` 字段生成 pi 的 `--tools` 参数。

#### Scenario: 类型层默认 tools
- **WHEN** `NodeConfig` 定义 `tools: [bash]`，实例未覆盖
- **THEN** executor SHALL 向 pi 传递 `--tools bash`

#### Scenario: 实例层覆盖 tools
- **WHEN** `NodeConfig` 定义 `tools: [bash]`，实例配置 `tools: [bash, read, edit, write]`
- **THEN** executor SHALL 使用实例配置，向 pi 传递 `--tools bash,read,edit,write`

#### Scenario: 空 tools 列表
- **WHEN** 实例配置 `tools: []`
- **THEN** executor SHALL 向 pi 传递 `--no-tools`

### Requirement: EDERA_IDENTITY 环境变量注入
Node executor SHALL 在启动 pi 进程时注入 `EDERA_IDENTITY` 环境变量，值为 `node:{node_id}`。

#### Scenario: 注入节点身份
- **WHEN** executor 执行节点实例 `llm-analyze`
- **THEN** executor SHALL 设置环境变量 `EDERA_IDENTITY=node:llm-analyze` 后启动 pi 进程

#### Scenario: Agent 调用 edera CLI
- **WHEN** pi 进程中的 agent 执行 `edera entity get stock:AAPL`
- **THEN** `edera` CLI SHALL 读取 `EDERA_IDENTITY` 环境变量，以 `node:llm-analyze` 身份执行权限检查

### Requirement: 按 NodeConfig type 分发执行
Node executor SHALL 根据 NodeConfig 的 type 字段分发到不同执行路径：`function` 走 `snapshot.handler_resolver` + importlib，`agent` 走 subprocess pi CLI，`dag` 走递归 DagRunner。MUST NOT 统一为 function node 执行路径。

#### Scenario: Function 节点走 snapshot handler resolver
- **WHEN** executor 执行 `FunctionNodeConfig` 类型节点
- **THEN** executor SHALL 通过 `snapshot.handler_resolver` 查询 handler metadata
- **AND** executor SHALL 通过 importlib 加载 handler 模块，调用 `run(ctx: HandlerContext)`

#### Scenario: Agent 节点走 subprocess
- **WHEN** executor 执行 `AgentNodeConfig` 类型节点
- **THEN** executor SHALL 启动 subprocess 调用 pi CLI，不走 handler resolver

#### Scenario: Dag 节点走递归 DagRunner
- **WHEN** executor 执行 `DagNodeConfig` 类型节点
- **THEN** executor SHALL 递归调用 DagRunner 执行目标 DAG

### Requirement: Agent 节点 workdir 和 session 分离
Node executor SHALL 为 agent 节点设置 subprocess cwd 为 `workdir`（用户配置），`--session-dir` 参数指向 server 决定的绝对路径 `${EDERA_DATA_DIR}/sessions/{dag_name}/{group}/{run_id}/`（`group` 为 session 组名，未声明时为 `instance_id`）。未配置 `workdir` 时 cwd SHALL 为该节点的 invocation 目录 `{session_dir}/invocations/{node_id}/`。MUST NOT 将 session 目录本身作为 cwd，MUST NOT 假设路径在客户端家目录下。

#### Scenario: Workdir 设置为 cwd
- **WHEN** agent 节点配置 `workdir: /path/to/project`
- **THEN** executor SHALL 设置 subprocess cwd 为 `/path/to/project`

#### Scenario: 未配置 workdir 时默认为 invocation 目录
- **WHEN** agent 节点未配置 `workdir`
- **THEN** executor SHALL 设置 subprocess cwd 为 `{session_dir}/invocations/{node_id}/`

#### Scenario: Session 路径由 server 管理
- **WHEN** agent 节点执行
- **THEN** executor SHALL 使用 server 决定的绝对路径作为 `--session-dir`，路径形如 `${EDERA_DATA_DIR}/sessions/{dag_name}/{group}/{run_id}/`
- **AND** executor MUST NOT 使用 `~/.rig/sessions/{...}` 或 `~/.edera/sessions/{...}` 路径模板

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

### Requirement: Session 引用解析
Node executor SHALL 在执行 agent 节点前解析实例的 `session` 字段：组名解析为当前 run 的组路径；`@latest` / `@list` 引用通过 session run 注册表解析为源组会话。未声明 `session` 的节点 SHALL 使用按 `instance_id` 推导的路径，行为不变。

#### Scenario: 组名解析为当前 run 组路径
- **WHEN** 实例声明 `session: task-1`，当前 run 为 `run-1`
- **THEN** executor SHALL 使用 `${EDERA_DATA_DIR}/sessions/{dag_name}/task-1/run-1/` 作为 session 目录

#### Scenario: 跨 DAG 引用经注册表解析
- **WHEN** 实例声明 `session: relay-main/task-1@latest`
- **THEN** executor SHALL 查询注册表获取源组最近 `completed` run 的 session id 与路径

#### Scenario: 未声明 session 行为不变
- **WHEN** 实例未声明 `session` 字段
- **THEN** executor SHALL 按 `instance_id` 推导 session 路径，与既有行为一致

