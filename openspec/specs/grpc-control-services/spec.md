---
capabilities:
  - cap.core.grpc-control-services
---
# grpc-control-services Specification

## Purpose
此规约记录 gRPC 控制面服务的 DAG 运行、系统控制、事件注入和 source repair task 行为。
## Requirements
### Requirement: DagService DAG 运行控制
`edera-server` SHALL 通过 `DagService` 提供 DAG run、stop 和 retry 操作。

#### Scenario: 启动 DAG run
- **WHEN** 客户端调用 `DagService.Run`
- **THEN** server SHALL 调用 `DagController.start_run("manual")` 并返回 run_id

#### Scenario: 启动时已有活跃 run
- **WHEN** 客户端调用 `DagService.Run` 且目标 DAG 已有活跃 run
- **THEN** server SHALL 返回 gRPC ALREADY_EXISTS 错误，包含活跃 run_id

#### Scenario: 停止指定 DAG
- **WHEN** 客户端调用 `DagService.Stop(dag_name, force)`
- **THEN** server SHALL 验证 DAG 存在，调用 `DagController.stop_current(dag_name, force)` 并返回结果

#### Scenario: 停止不存在的 DAG
- **WHEN** 客户端调用 `DagService.Stop` 且 dag_name 不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

#### Scenario: 重试 DAG 节点
- **WHEN** 客户端调用 `DagService.Retry(dag_name, run_id, node_ids, mode, payload)`
- **THEN** server SHALL 验证 DAG 存在和参数合法性，调用 `DagController.retry_node()` 并返回重试结果

#### Scenario: 重试时已有活跃 run
- **WHEN** 客户端调用 `DagService.Retry` 且目标 DAG 已有活跃 run
- **THEN** server SHALL 返回 gRPC ALREADY_EXISTS 错误

#### Scenario: 重试时 run 不存在
- **WHEN** 客户端调用 `DagService.Retry` 且 run_id 对应的 run 不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

#### Scenario: 重试参数非法
- **WHEN** 客户端调用 `DagService.Retry` 且 node_ids 为空或格式非法
- **THEN** server SHALL 返回 gRPC INVALID_ARGUMENT 错误

### Requirement: SystemService scheduler 控制
`edera-server` SHALL 通过 `SystemService` 提供 scheduler pause、resume 和 status 操作。

#### Scenario: 暂停 scheduler
- **WHEN** 客户端调用 `SystemService.PauseScheduler`
- **THEN** server SHALL 调用 `DagController.pause_scheduler()` 并返回当前状态

#### Scenario: 恢复 scheduler
- **WHEN** 客户端调用 `SystemService.ResumeScheduler`
- **THEN** server SHALL 调用 `DagController.resume_scheduler()` 并返回当前状态

#### Scenario: 查询 scheduler status
- **WHEN** 客户端调用 `SystemService.SchedulerStatus`
- **THEN** server SHALL 返回 scheduler state 和 active runs

### Requirement: SystemService source repair task
`edera-server` SHALL 通过 `SystemService` 提供 source repair task 创建操作。

#### Scenario: 创建 repair task
- **WHEN** 客户端调用 `SystemService.CreateRepairTask(source_name)`
- **THEN** server SHALL 验证 source 存在且处于 escalated 状态，生成 repair task JSON 文件，更新 briefing metadata

#### Scenario: source 未 escalated
- **WHEN** 客户端调用 `SystemService.CreateRepairTask` 且 source 未处于 escalated 状态
- **THEN** server SHALL 返回 gRPC FAILED_PRECONDITION 错误

#### Scenario: source 不存在
- **WHEN** 客户端调用 `SystemService.CreateRepairTask` 且 source_name 不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

### Requirement: EventService 事件注入
`edera-server` SHALL 通过 `EventService` 提供事件注入操作。

#### Scenario: 注入事件
- **WHEN** 客户端调用 `EventService.Emit(event, payload_json)`
- **THEN** server SHALL 调用 `DagController.emit(...)` 并返回受影响的 DAG run ids
