## MODIFIED Requirements

### Requirement: Session 路径结构
Agent 节点执行时 SHALL 使用 server 管理的 `${EDERA_DATA_DIR}/sessions/{dag_name}/{group}/{run_id}/` 作为 session 目录，其中 `group` 为实例声明的 session 组名；未声明 `session` 的实例 `group` 取 `instance_id`，路径与既有行为一致。

#### Scenario: 首次执行创建 session 目录
- **WHEN** agent 节点实例声明 `session: task-1` 并在 run `run-20260524-001` 中作为组内首个节点执行
- **THEN** 系统 SHALL 创建目录 `${EDERA_DATA_DIR}/sessions/{dag_name}/task-1/run-20260524-001/`

#### Scenario: Session 路径确定性
- **WHEN** 同一节点在同一 run 中重复执行（如重试）
- **THEN** 系统 SHALL 复用已有的 session 目录，不创建新目录

#### Scenario: 未声明 session 的节点路径不变
- **WHEN** agent 节点实例未声明 `session` 字段
- **THEN** 系统 SHALL 使用 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/{run_id}/`，行为与历史一致

## ADDED Requirements

### Requirement: Session 组关联声明
`DagNodeInstance.config` SHALL 支持 `session` 字段（可选字符串）声明会话关联：同 DAG 组名 `<group>`，或跨 DAG 有向引用 `<dag_name>/<group>@latest` / `<dag_name>/<group>@list`。

#### Scenario: 同 DAG 组名声明
- **WHEN** 同一 DAG 中两个 agent 实例均声明 `session: task-1`
- **THEN** 两个实例 SHALL 共享同一 session 组

#### Scenario: 跨 DAG 有向引用声明
- **WHEN** agent 实例声明 `session: relay-main/task-1@latest`
- **THEN** 该实例 SHALL 解析 `relay-main` DAG 中 `task-1` 组的会话，自身不创建新组

### Requirement: Session 组共享与续接
同组 agent 节点在一次 DAG run 中 SHALL 共享同一会话：组内首个执行的节点创建会话，系统捕获其 session id 并登记；组内后续节点 SHALL 以已登记的 session id 精确续接同一会话。

#### Scenario: 首个节点创建会话
- **WHEN** 组 `task-1` 在当前 run 中尚无会话，节点 B 首先执行
- **THEN** B SHALL 新建会话，系统 SHALL 捕获 session id 并登记到注册表

#### Scenario: 后续节点精确续接
- **WHEN** 组 `task-1` 在当前 run 中已有登记的 session id，节点 D 执行
- **THEN** D SHALL 以该 session id 续接同一会话，携带组内先前节点的完整上下文

### Requirement: Session 组串行
系统 SHALL 保证同一 session 组同一时刻至多一个 agent 进程在写：为每个组自动配置 `session:{dag_name}/{group}`（permits=1）的 resource，组内节点及跨 DAG 引用方执行前 MUST 先获取该 resource。等待时长计入节点 `timeout_seconds`，超时节点失败。

#### Scenario: 同 DAG 并行分支串行化
- **WHEN** `a→B`、`a→D` 拓扑下 B、D 同组且同时就绪
- **THEN** 系统 SHALL 串行执行 B 和 D，两个 agent 进程的运行时间不重叠

#### Scenario: 跨 DAG 引用方等待
- **WHEN** 引用方节点解析 `relay-main/task-1@latest` 时源组的 resource 正被持有
- **THEN** 引用方 SHALL 阻塞等待直到 resource 释放

#### Scenario: 等待超时
- **WHEN** 引用方等待源组 resource 的时长超过节点 `timeout_seconds`
- **THEN** 该节点 SHALL 以失败结束，错误信息指明等待 session 组超时

#### Scenario: 用户零配置
- **WHEN** 用户仅声明 `session` 字段，未配置任何 resource
- **THEN** 组串行 SHALL 自动生效，无需用户额外配置

### Requirement: Session run 注册表
系统 SHALL 在数据库中登记每个 session 组的 run 记录，包含 `dag_name`、`group`、`run_id`、`session_id`、`status`、`path`。会话创建时记录 `active`，所属 DAG run 结束时落 `completed` 或 `failed`。daemon 启动时 SHALL 将不属于任何活跃 run 的 `active` 记录批量落 `failed`。

#### Scenario: 创建时登记 active
- **WHEN** 组内首个节点创建会话
- **THEN** 注册表 SHALL 新增 status 为 `active` 的记录

#### Scenario: Run 结束更新状态
- **WHEN** 所属 DAG run 成功结束
- **THEN** 该记录 status SHALL 更新为 `completed`

#### Scenario: 启动对账清理残留
- **WHEN** daemon 启动时存在 `active` 记录且其 run_id 不属于任何活跃 run
- **THEN** 系统 SHALL 将这些记录批量落 `failed`

### Requirement: 跨 DAG latest 解析
`@latest` 引用 SHALL 解析为源组在注册表中最近一次 `completed` 的 run 的会话（session id 与路径）。无 `completed` 记录时节点失败。

#### Scenario: 解析到最近完成的 run
- **WHEN** 引用方节点声明 `session: relay-main/task-1@latest`，源组有多条 `completed` 记录
- **THEN** 系统 SHALL 解析到其中最近的一条，引用方以其 session id 续接

#### Scenario: 无可用记录
- **WHEN** 源组在注册表中无 `completed` 记录
- **THEN** 引用方节点 SHALL 以失败结束，错误信息指明 session 不存在

### Requirement: List 解析与消费账本
`@list` 引用 SHALL 解析为源组按时间排序的 run 列表，每项含 `run_id`、`session_id`、`consumed` 标记。系统 SHALL 维护消费账本记录 `(source_session_id, consumer)`：引用方节点成功完成时自动登记，失败或降级输出不登记。引用方无输入时默认取最旧的未消费项；输入指定 `run_id` 时取该项；输入 `all_unconsumed` 时取全部未消费项。

#### Scenario: 默认取最旧未消费
- **WHEN** `@list` 引用方节点无输入执行，源组存在未消费记录
- **THEN** 系统 SHALL 选取其中最旧的一条供其续接

#### Scenario: 成功后登记消费
- **WHEN** 引用方节点成功完成（结构化输出校验通过）
- **THEN** 消费账本 SHALL 登记该 `(source_session_id, consumer)`，后续 `@list` 解析中该项 `consumed` 为 true

#### Scenario: 失败不登记可重试
- **WHEN** 引用方节点失败或输出降级
- **THEN** 消费账本 MUST NOT 登记，该 session 在下次解析时仍为未消费

#### Scenario: 输入显式指定 run
- **WHEN** 引用方节点输入指定 `run_id`
- **THEN** 系统 SHALL 选取该 run 的会话，忽略 consumed 标记

## REMOVED Requirements

### Requirement: Session 目录独立管理
**Reason**: TTL/size 清理与被引用延迟清理从未实现，本变更不承诺该能力，移除以保持规格与系统一致。
**Migration**: 清理能力留待后续独立变更；当前 session 目录长期保留。

### Requirement: session_dir 配置
**Reason**: `session_dir` 字段废弃，会话关联由 `session` 字段（组名 + 有向引用）承载，术语统一为 session。
**Migration**: 使用 `DagNodeInstance.config.session` 字段；绝对路径定制存储位置的能力不再提供。

### Requirement: 自动 resume 判定
**Reason**: 共享会话目录下按 `.jsonl` 存在性判定续接有歧义，可能续接到错误会话。
**Migration**: 续接改为以注册表登记的 session id 显式定位（见 agent-executor 的 Pi CLI subprocess 配置）。

### Requirement: Payload 动态覆盖
**Reason**: `resume_session` payload 在系统中无消费者，属死路径；resume 通过复用原 run_id 与确定性路径实现。
**Migration**: 无需迁移；resume API 行为不变。
