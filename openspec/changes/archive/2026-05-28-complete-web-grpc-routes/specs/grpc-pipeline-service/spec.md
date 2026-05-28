## ADDED Requirements

### Requirement: PipelineService 全局 pipeline 控制
`edera-server` SHALL 通过 `PipelineService` 提供全局 pipeline 的 run/pause/resume/stop 操作。

#### Scenario: 启动 pipeline run
- **WHEN** 客户端调用 `PipelineService.Run`
- **THEN** server SHALL 调用 PipelineController.start_run("manual") 并返回 cycle_id

#### Scenario: 启动时已有活跃 run
- **WHEN** 客户端调用 `PipelineService.Run` 且已有活跃 run
- **THEN** server SHALL 返回 gRPC ALREADY_EXISTS 错误，包含活跃 cycle_id

#### Scenario: 暂停 pipeline
- **WHEN** 客户端调用 `PipelineService.Pause`
- **THEN** server SHALL 调用 PipelineController.pause_scheduler() 并返回当前状态

#### Scenario: 恢复 pipeline
- **WHEN** 客户端调用 `PipelineService.Resume`
- **THEN** server SHALL 调用 PipelineController.resume_scheduler() 并返回当前状态

#### Scenario: 停止 pipeline
- **WHEN** 客户端调用 `PipelineService.Stop`
- **THEN** server SHALL 调用 PipelineController.stop_current() 并返回停止的 cycle_id

#### Scenario: 查询 pipeline status
- **WHEN** 客户端调用 `PipelineService.Status`
- **THEN** server SHALL 返回 PipelineController 当前状态（scheduler state、active runs）

### Requirement: PipelineService DAG 级控制
`edera-server` SHALL 通过 `PipelineService` 提供 DAG 级别的 stop 和 retry 操作。

#### Scenario: 停止指定 DAG
- **WHEN** 客户端调用 `PipelineService.DagStop(dag_name, force)`
- **THEN** server SHALL 验证 DAG 存在，调用 PipelineController.stop_current(dag_name, force) 并返回结果

#### Scenario: 停止不存在的 DAG
- **WHEN** 客户端调用 `PipelineService.DagStop` 且 dag_name 不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

#### Scenario: 重试 DAG 节点
- **WHEN** 客户端调用 `PipelineService.DagRetry(dag_name, cycle_id, node_ids, mode, payload)`
- **THEN** server SHALL 验证 DAG 存在和参数合法性，调用 PipelineController.retry_node() 并返回重试结果

#### Scenario: 重试时已有活跃 run
- **WHEN** 客户端调用 `PipelineService.DagRetry` 且目标 DAG 已有活跃 run
- **THEN** server SHALL 返回 gRPC ALREADY_EXISTS 错误

#### Scenario: 重试时 cycle 不存在
- **WHEN** 客户端调用 `PipelineService.DagRetry` 且 cycle_id 对应的 run 不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

#### Scenario: 重试参数非法
- **WHEN** 客户端调用 `PipelineService.DagRetry` 且 node_ids 为空或格式非法
- **THEN** server SHALL 返回 gRPC INVALID_ARGUMENT 错误

### Requirement: PipelineService source repair task
`edera-server` SHALL 通过 `PipelineService` 提供 source repair task 创建操作。

#### Scenario: 创建 repair task
- **WHEN** 客户端调用 `PipelineService.CreateRepairTask(source_name)`
- **THEN** server SHALL 验证 source 存在且处于 escalated 状态，生成 repair task JSON 文件，更新 briefing metadata

#### Scenario: source 未 escalated
- **WHEN** 客户端调用 `PipelineService.CreateRepairTask` 且 source 未处于 escalated 状态
- **THEN** server SHALL 返回 gRPC FAILED_PRECONDITION 错误

#### Scenario: source 不存在
- **WHEN** 客户端调用 `PipelineService.CreateRepairTask` 且 source_name 不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误
