## Purpose

定义管道运行控制能力，包括运行记录、节点状态记录、手动运行、并发拒绝、调度暂停恢复、停止当前运行和状态展示。
## Requirements
### Requirement: Persistent pipeline runs
系统 SHALL 持久化每次管道运行的 cycle_id、dag_name、触发来源、状态、开始时间、结束时间和错误信息。

#### Scenario: Record manual run with dag_name
- **WHEN** 用户手动触发指定 DAG 运行
- **THEN** 系统 MUST 创建一条包含 `dag_name` 和 trigger 为 `manual` 的运行记录

#### Scenario: Record failed run with dag_name
- **WHEN** 指定 DAG 运行失败
- **THEN** 系统 MUST 将运行记录状态标记为 `failed` 并保存错误信息和 `dag_name`

### Requirement: Persistent node runs
系统 SHALL 持久化每次管道运行中各 Node 的状态、开始时间、结束时间和错误信息。

#### Scenario: Record node failure
- **WHEN** 某个 Node 执行失败但 DAG 继续降级运行
- **THEN** 系统 MUST 保存该 Node 的 `failed` 状态和错误信息

### Requirement: Manual run control
系统 SHALL 支持用户从 Web 控制台或 API 手动运行指定 DAG。

#### Scenario: Start manual run for named DAG
- **WHEN** 没有该 DAG 的运行中任务且用户触发手动运行
- **THEN** 系统 SHALL 启动指定 DAG 并返回新 cycle_id

#### Scenario: Reject concurrent run for same DAG
- **WHEN** 指定 DAG 已有运行中任务且用户再次触发手动运行
- **THEN** 系统 MUST 拒绝并返回当前运行中的 cycle_id

### Requirement: Scheduler pause and resume
系统 SHALL 支持用户暂停和恢复定时调度。

#### Scenario: Pause scheduler
- **WHEN** 用户点击暂停调度
- **THEN** 系统 SHALL 暂停后续定时触发，但不取消当前正在运行的周期

#### Scenario: Resume scheduler
- **WHEN** 用户点击恢复调度
- **THEN** 系统 SHALL 恢复后续定时触发

### Requirement: Stop current run
系统 SHALL 支持用户停止指定 DAG 的当前运行。

#### Scenario: Stop running cycle for named DAG
- **WHEN** 用户请求停止指定 DAG 且该 DAG 存在运行中任务
- **THEN** 系统 SHALL 请求取消该 DAG 的运行，并将运行记录最终标记为 `cancelled` 或 `failed`

#### Scenario: Stop with no active run for named DAG
- **WHEN** 用户请求停止指定 DAG 且该 DAG 没有运行中任务
- **THEN** 系统 SHALL 返回无活动运行状态

### Requirement: Runtime status display
系统 SHALL 展示指定 DAG 的当前运行状态和最近运行记录。

#### Scenario: View per-DAG pipeline status
- **WHEN** 用户查询指定 DAG 的管道状态
- **THEN** 系统 SHALL 展示该 DAG 的 scheduler 是否活跃、当前 cycle_id 和该 DAG 的最近运行列表

### Requirement: Source recovery execution recording
系统 SHALL 将源级自动恢复尝试关联到现有管道运行上下文，MUST 通过 `PipelineRun.cycle_id`、对应 source 的 `NodeRun` 和 `Briefing.metadata_` 追溯恢复结果。

#### Scenario: Record successful recovery in pipeline context
- **WHEN** 某信息源在同一 cycle 内经过自动恢复后成功
- **THEN** 系统 SHALL 将对应 `NodeRun` 的最终状态记录为 `succeeded`，并在 `Briefing.metadata_` 中记录该 source 的恢复尝试摘要

#### Scenario: Record exhausted recovery in pipeline context
- **WHEN** 某信息源自动恢复尝试耗尽后仍失败
- **THEN** 系统 SHALL 将对应 `NodeRun` 的最终状态记录为 `failed`，并在 `Briefing.metadata_` 中记录 attempt_count、恢复失败原因和升级状态

#### Scenario: Preserve cycle traceability for repair handoff
- **WHEN** 用户生成外部修复任务交接包
- **THEN** 系统 SHALL 在交接包中包含最近失败 `PipelineRun.cycle_id` 和对应 `NodeRun` 错误，以便外部辅助能力追溯执行上下文

### Requirement: Node Graph runtime status source
系统 SHALL 为 Node Graph 编辑器提供可映射到节点名称的运行状态数据。

#### Scenario: Load graph runtime status
- **WHEN** Node Graph 编辑器请求运行状态
- **THEN** 系统 SHALL 返回当前运行和最近运行中各 Node 的状态、错误信息和 cycle_id

#### Scenario: Unknown draft node status
- **WHEN** Node Graph 草稿中存在尚未保存或没有运行记录的节点
- **THEN** 系统 SHALL 将该节点状态展示为 `unknown`，不得伪造运行结果

