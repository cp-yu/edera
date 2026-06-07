## MODIFIED Requirements

### Requirement: Manual run control

系统 SHALL 支持用户从 Web 控制台或 API 手动运行指定 DAG。DAG run 启动时 MUST 由 DagController 从 DB-backed source of truth 构建 `DAG execution closure` 和 `DagExecutionSnapshot`，MUST NOT 依赖全量 `RuntimeControlSnapshot` DAG/Node map。

#### Scenario: Start manual run for named DAG

- **WHEN** 没有该 DAG 的运行中任务且用户触发手动运行
- **THEN** 系统 SHALL 构建指定 DAG 的 `DagExecutionSnapshot`，启动指定 DAG 并返回新 run_id

#### Scenario: Reject concurrent run for same DAG

- **WHEN** 指定 DAG 已有运行中任务且用户再次触发手动运行
- **THEN** 系统 MUST 拒绝并返回当前运行中的 run_id

### Requirement: TriggerExecutor 统一调度

系统 SHALL 通过全局 TriggerExecutor 统一管理所有 DAG/Node 的调度。系统 MUST NOT 创建独立 interval scheduler job；调度完全由 Trigger Entity + cron emitter 驱动。TriggerExecutor SHALL 位于 committed `RuntimeControlSnapshot` 中。

#### Scenario: 启动时不注册 interval job

- **WHEN** edera-server 启动
- **THEN** 系统不创建独立 interval scheduler job；调度完全由 Trigger Entity + cron emitter 驱动

#### Scenario: 手动运行走 emit 路径

- **WHEN** 用户通过 API 或 CLI 手动运行 DAG
- **THEN** 系统调用 `emit("manual:dag:<name>")` 而非直接调用 `start_run()`

### Requirement: Startup does not run DAG
`DagController.start()` SHALL initialize runtime dependencies, `RuntimeControlSnapshot`, scheduler state and cron loop without starting any DAG run or loading all DAG/Node definitions.

#### Scenario: Controller start is idle
- **WHEN** `DagController.start()` completes
- **THEN** no `DagRun` record SHALL be created by startup
- **AND** no DAG SHALL appear in `active_runs` solely because the controller started
- **AND** system MUST NOT load all DAG/Node configs solely because the controller started

## ADDED Requirements

### Requirement: Node trigger target includes DAG name
Node trigger targets SHALL use `node:<dag_name>/<node_id>`. The system MUST NOT locate node trigger targets by globally scanning all DAG definitions.

#### Scenario: Node trigger with DAG path
- **WHEN** TriggerExecutor fires target `node:analysis/fetch-news`
- **THEN** DagController SHALL load DAG `analysis` from DB
- **AND** DagController SHALL resolve `fetch-news` only within DAG `analysis`

#### Scenario: Node trigger missing DAG path
- **WHEN** TriggerExecutor fires target `node:fetch-news`
- **THEN** system SHALL reject the target as invalid

#### Scenario: Same node alias in different DAGs
- **WHEN** DAG `a` and DAG `b` both contain node alias `fetch-news`
- **THEN** target `node:a/fetch-news` SHALL resolve only the node in DAG `a`
