## MODIFIED Requirements

### Requirement: gRPC Service 定义
`edera-server` SHALL 暴露 gRPC 服务，包含 `EntityService`、`DagService`、`NodeService`、`SystemService`、`GraphService`、`ConfigService`、`QueryService`、`EventService` 八个 service。`PipelineService` 已废弃，职责分散到 `DagService`、`EventService`、`SystemService`。Proto package 为 `edera.v1`，文件路径 `proto/edera.proto`。

#### Scenario: EntityService 提供 CRUD
- **WHEN** 客户端调用 `EntityService.Create`
- **THEN** server SHALL 创建 entity 并返回创建结果

#### Scenario: EntityService 提供 Query
- **WHEN** 客户端调用 `EntityService.Query` 携带表达式 `type=analysis AND confidence>0.8`
- **THEN** server SHALL 解析表达式并返回满足条件的 entity 列表

#### Scenario: EntityService 保留 List
- **WHEN** 客户端调用 `EntityService.List` 携带 `EntityQuery{type: "stock"}`
- **THEN** server SHALL 返回该类型的所有 entity，不解析任何表达式

#### Scenario: DagService 提供运行和查询
- **WHEN** 客户端调用 `DagService.Run`
- **THEN** server SHALL 启动 DAG 执行并返回 `DagRunRef{run_id: "..."}`

#### Scenario: DagService 提供停止和重试
- **WHEN** 客户端调用 `DagService.Stop` 或 `DagService.Retry`
- **THEN** server SHALL 执行对应操作并返回结果

#### Scenario: EventService 提供事件注入
- **WHEN** 客户端调用 `EventService.Emit`
- **THEN** server SHALL 注入事件到 EventGroup 并触发 trigger 表达式评估

#### Scenario: SystemService 提供 scheduler 控制
- **WHEN** 客户端调用 `SystemService.PauseScheduler`
- **THEN** server SHALL 暂停 TriggerExecutor 的 cron 循环

#### Scenario: GraphService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_GraphServiceServicer_to_server` 注册 GraphService 实现

#### Scenario: ConfigService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_ConfigServiceServicer_to_server` 注册 ConfigService 实现

#### Scenario: QueryService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_QueryServiceServicer_to_server` 注册 QueryService 实现

#### Scenario: EventService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_EventServiceServicer_to_server` 注册 EventService 实现

#### Scenario: Proto package 为 edera.v1
- **WHEN** 检查 `proto/edera.proto` 文件
- **THEN** 文件 SHALL 声明 `package edera.v1`
- **AND** SHALL NOT 包含任何 `rig.v1` 引用

## ADDED Requirements

### Requirement: DagRunRef 使用 run_id
Proto message `DagRunRef` SHALL 使用 `run_id` 字段标识 DAG 执行实例，不再使用 `cycle_id`。

#### Scenario: DagRunRef 字段定义
- **WHEN** 检查 `proto/edera.proto` 中的 `DagRunRef` message
- **THEN** message SHALL 包含 `string run_id = 1;` 字段
- **AND** SHALL NOT 包含 `cycle_id` 字段

#### Scenario: DagService.Run 返回 run_id
- **WHEN** 客户端调用 `DagService.Run`
- **THEN** server SHALL 返回 `DagRunRef{run_id: "<uuid>"}`

