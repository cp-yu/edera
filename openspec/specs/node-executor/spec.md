---
capabilities:
  - cap.operations.node-executor
---
# node-executor Specification

## Purpose
此规约记录变更 project-mvp 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
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

Node executor SHALL 从 Entity Store 加载 Node Entity，根据 handler registry 查找执行入口。MUST NOT 依赖 Entity attributes 中的 `type: function/llm` 区分。

#### Scenario: 加载 Node Entity 并执行

- **WHEN** DAG Runner 调度执行一个 Node Entity
- **THEN** executor 从 Entity Store 读取该 Entity 的 attributes，提取 `handler` 字段，从 registry 查找执行入口

#### Scenario: Node Entity 无 handler 且不在 registry

- **WHEN** executor 尝试执行一个 attributes 中无 `handler` 的 Entity，且其类型不在 handler registry 中
- **THEN** executor 返回错误 "Entity is not executable: no registered handler"

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

### Requirement: Session_dir 解析与传递
Node executor SHALL 解析 `session_dir` 配置（支持引用格式），将解析后的绝对路径传递给 pi 的 `--session-dir` 参数。

#### Scenario: 解析 latest 引用
- **WHEN** 实例配置 `session_dir: "sandbox:llm-analyze:latest"`
- **THEN** executor SHALL 查询 `llm-analyze` 节点最近一次执行的 sandbox 路径，传递给 pi

#### Scenario: 解析指定 run 引用
- **WHEN** 实例配置 `session_dir: "sandbox:llm-analyze:run-20260524-001"`
- **THEN** executor SHALL 构造路径 `workspace_root/sandbox/llm-analyze/run-20260524-001/sessions/`，传递给 pi

#### Scenario: 绝对路径直接传递
- **WHEN** 实例配置 `session_dir: "/data/persistent/advisor-session"`
- **THEN** executor SHALL 直接将该路径传递给 pi 的 `--session-dir`

### Requirement: 自动 --continue 判定
Node executor SHALL 检测 session_dir 中是否存在 `.jsonl` 文件，存在则向 pi 传递 `--continue` flag。

#### Scenario: 存在 session 文件
- **WHEN** session_dir 中存在 `*.jsonl` 文件
- **THEN** executor SHALL 向 pi 传递 `--continue` flag

#### Scenario: 不存在 session 文件
- **WHEN** session_dir 为空目录或仅包含非 `.jsonl` 文件
- **THEN** executor SHALL 不传 `--continue`，pi 创建新 session

### Requirement: 按 NodeConfig type 分发执行
Node executor SHALL 根据 NodeConfig 的 type 字段分发到不同执行路径：`function` 走 handler registry，`agent` 走 subprocess pi CLI，`dag` 走递归 DagRunner。MUST NOT 统一为 function node 执行路径。

#### Scenario: Function 节点走 handler registry
- **WHEN** executor 执行 `FunctionNodeConfig` 类型节点
- **THEN** executor SHALL 通过 importlib 从 handler registry 加载 handler 模块，调用 `run(ctx: HandlerContext)`

#### Scenario: Agent 节点走 subprocess
- **WHEN** executor 执行 `AgentNodeConfig` 类型节点
- **THEN** executor SHALL 启动 subprocess 调用 pi CLI，不走 handler registry

#### Scenario: Dag 节点走递归 DagRunner
- **WHEN** executor 执行 `DagNodeConfig` 类型节点
- **THEN** executor SHALL 递归调用 DagRunner 执行目标 DAG

### Requirement: Agent 节点 workdir 和 session 分离
Node executor SHALL 为 agent 节点设置 subprocess cwd 为 `workdir`（用户配置），`--session-dir` 参数指向 server 决定的绝对路径 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/{run_id}/`。MUST NOT 将 `session_dir` 作为 cwd，MUST NOT 假设路径在客户端家目录下。

#### Scenario: Workdir 设置为 cwd
- **WHEN** agent 节点配置 `workdir: /path/to/project`
- **THEN** executor SHALL 设置 subprocess cwd 为 `/path/to/project`

#### Scenario: Session 路径由 server 管理
- **WHEN** agent 节点执行
- **THEN** executor SHALL 使用 server 决定的绝对路径作为 `--session-dir`，路径形如 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/{run_id}/`
- **AND** executor MUST NOT 使用 `~/.rig/sessions/{...}` 或 `~/.edera/sessions/{...}` 路径模板
