## MODIFIED Requirements

### Requirement: gRPC Service 定义
`edera-server` SHALL 暴露 gRPC 服务，包含 `EntityService`、`DagService`、`NodeService`、`SystemService`、`GraphService`、`ConfigService`、`QueryService`、`PipelineService` 八个 service。Proto package 为 `edera.v1`，文件路径 `proto/edera.proto`。本 capability 接替原 `rig-daemon-grpc`。

#### Scenario: EntityService 提供 CRUD
- **WHEN** 客户端调用 `EntityService.Create`
- **THEN** server SHALL 创建 entity 并返回创建结果

#### Scenario: EntityService 提供 Query
- **WHEN** 客户端调用 `EntityService.Query` 携带表达式 `type=analysis AND confidence>0.8`
- **THEN** server SHALL 解析表达式并返回满足条件的 entity 列表

#### Scenario: EntityService 保留 List
- **WHEN** 客户端调用 `EntityService.List` 携带 `EntityQuery{type: "stock"}`
- **THEN** server SHALL 返回该类型的所有 entity，不解析任何表达式

#### Scenario: DagService 提供触发和查询
- **WHEN** 客户端调用 `DagService.Trigger`
- **THEN** server SHALL 启动 DAG 执行并返回 cycle_id

#### Scenario: GraphService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_GraphServiceServicer_to_server` 注册 GraphService 实现

#### Scenario: ConfigService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_ConfigServiceServicer_to_server` 注册 ConfigService 实现

#### Scenario: QueryService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_QueryServiceServicer_to_server` 注册 QueryService 实现

#### Scenario: PipelineService 注册到 server
- **WHEN** `edera-server` 启动
- **THEN** server SHALL 通过 `add_PipelineServiceServicer_to_server` 注册 PipelineService 实现

#### Scenario: Proto package 为 edera.v1
- **WHEN** 检查 `proto/edera.proto` 文件
- **THEN** 文件 SHALL 声明 `package edera.v1`
- **AND** SHALL NOT 包含任何 `rig.v1` 引用
