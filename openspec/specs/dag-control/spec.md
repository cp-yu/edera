## Purpose

定义 DAG 运行控制能力，包括运行记录、节点状态记录、手动运行、并发拒绝、调度暂停恢复、停止当前运行和状态展示。
## Requirements
### Requirement: Persistent DAG runs

系统 SHALL 持久化每次 DAG run 的 run_id、dag_name、source、状态、开始时间、结束时间、错误信息和 retry_of（nullable）。

#### Scenario: Record retry run

- **WHEN** 系统创建 retry run
- **THEN** 系统 MUST 创建一条 DagRun 记录，source 为 `"retry"`，`retry_of` 指向被重试的原始 run_id

#### Scenario: Record manual run with dag_name

- **WHEN** 用户手动触发指定 DAG 运行
- **THEN** 系统 MUST 创建一条包含 `dag_name` 和 source 为 `manual` 的运行记录，`retry_of` 为 null

### Requirement: Persistent node runs
系统 SHALL 持久化每次 DAG run 中各 Node 的状态、开始时间、结束时间和错误信息。

#### Scenario: Record node failure
- **WHEN** 某个 Node 执行失败但 DAG 继续降级运行
- **THEN** 系统 MUST 保存该 Node 的 `failed` 状态和错误信息

### Requirement: Manual run control

系统 SHALL 支持用户从 Web 控制台或 API 手动运行指定 DAG。Handler 注册 MUST 从 bootstrap registry 获取，MUST NOT 硬编码 handler 字典。

#### Scenario: Start manual run for named DAG

- **WHEN** 没有该 DAG 的运行中任务且用户触发手动运行
- **THEN** 系统 SHALL 从 handler registry 构建 executor，启动指定 DAG 并返回新 run_id

#### Scenario: Reject concurrent run for same DAG

- **WHEN** 指定 DAG 已有运行中任务且用户再次触发手动运行
- **THEN** 系统 MUST 拒绝并返回当前运行中的 run_id

### Requirement: Stop current run

系统 SHALL 支持用户停止指定 DAG 的当前运行，MUST 支持 soft stop（等当前节点完成）和 hard stop（立即 cancel）两种模式。

#### Scenario: Soft stop 指定 DAG

- **WHEN** 用户请求停止指定 DAG（`force: false` 或无 body）且该 DAG 存在运行中任务
- **THEN** 系统 MUST 设置 stop event，等待当前正在执行的节点完成后终止 run，将运行记录标记为 `cancelled`

#### Scenario: Hard stop 指定 DAG

- **WHEN** 用户请求停止指定 DAG（`force: true`）且该 DAG 存在运行中任务
- **THEN** 系统 MUST 立即 cancel 运行 task，将运行记录标记为 `cancelled`

#### Scenario: Stop with no active run for named DAG

- **WHEN** 用户请求停止指定 DAG 且该 DAG 没有运行中任务
- **THEN** 系统 SHALL 返回无活动运行状态

### Requirement: Runtime status display
系统 SHALL 展示指定 DAG 的当前运行状态和最近运行记录。前端 SHALL 在 DAG 运行期间以固定间隔（2s）轮询节点运行状态，运行结束后停止轮询。

#### Scenario: View per-DAG run status
- **WHEN** 用户查询指定 DAG 的运行状态
- **THEN** 系统 SHALL 返回调度器状态、当前 run_id 和最近运行记录

#### Scenario: Poll node status during active run
- **WHEN** DAG 处于运行中状态
- **THEN** 前端 SHALL 每 2 秒刷新一次 `GET /api/graph/runtime-status`，画布节点实时反映最新状态

#### Scenario: Stop polling after run completes
- **WHEN** DAG 运行结束（`current_run_id` 变为 null）
- **THEN** 前端 SHALL 停止对 `GET /api/graph/runtime-status` 的轮询

### Requirement: Source recovery execution recording
系统 SHALL 将源级自动恢复尝试关联到现有 DAG run 上下文，MUST 通过 `DagRun.run_id`、对应 source 的 `NodeRun` 和 `Briefing.metadata_` 追溯恢复结果。

#### Scenario: Record successful recovery in DAG run context
- **WHEN** 某信息源在同一 run 内经过自动恢复后成功
- **THEN** 系统 SHALL 将对应 `NodeRun` 的最终状态记录为 `succeeded`，并在 `Briefing.metadata_` 中记录该 source 的恢复尝试摘要

#### Scenario: Record exhausted recovery in DAG run context
- **WHEN** 某信息源自动恢复尝试耗尽后仍失败
- **THEN** 系统 SHALL 将对应 `NodeRun` 的最终状态记录为 `failed`，并在 `Briefing.metadata_` 中记录 attempt_count、恢复失败原因和升级状态

#### Scenario: Preserve run traceability for repair handoff
- **WHEN** 用户生成外部修复任务交接包
- **THEN** 系统 SHALL 在交接包中包含最近失败 `DagRun.run_id` 和对应 `NodeRun` 错误，以便外部辅助能力追溯执行上下文

### Requirement: Node Graph runtime status source
系统 SHALL 为 Node Graph 编辑器提供可映射到节点名称的运行状态数据。

#### Scenario: Load graph runtime status
- **WHEN** Node Graph 编辑器请求运行状态
- **THEN** 系统 SHALL 返回当前运行和最近运行中各 Node 的状态、错误信息和 run_id

#### Scenario: Unknown draft node status
- **WHEN** Node Graph 草稿中存在尚未保存或没有运行记录的节点
- **THEN** 系统 SHALL 将该节点状态展示为 `unknown`，不得伪造运行结果

### Requirement: DAG 运行 API 增加 inputs 参数
系统 SHALL 在 DAG 触发 API 中支持 `inputs` 参数，允许外部传入 DAG 声明的输入参数。

#### Scenario: API 传递 inputs
- **WHEN** 客户端 POST `/api/dags/my-dag/run` 并携带 `{"inputs": {"ticker": "00100.HK"}}`
- **THEN** 系统 SHALL 将 inputs 传递给 DAG 运行时，绑定的 source 节点使用传入值

#### Scenario: 无 inputs 参数时正常运行
- **WHEN** 客户端 POST `/api/dags/my-dag/run` 不携带 `inputs` 参数
- **THEN** 系统 SHALL 正常启动 DAG，source 节点从 `source_names` 拉取数据

### Requirement: TriggerExecutor 统一调度

系统 SHALL 通过 TriggerExecutor 统一管理所有 DAG/Node 的调度。系统 MUST 不再使用 APScheduler 全局 interval 调度。

#### Scenario: 启动时不注册 interval job

- **WHEN** edera-server 启动
- **THEN** 系统不创建 APScheduler interval job；调度完全由 trigger entity + cron emitter 驱动

#### Scenario: 手动运行走 emit 路径

- **WHEN** 用户通过 API 或 CLI 手动运行 DAG
- **THEN** 系统调用 `emit("manual:dag:<name>")` 而非直接调用 `start_run()`
