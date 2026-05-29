# grpc-query-service Specification

## Purpose
此规约记录变更 complete-web-grpc-routes 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: QueryService briefing 查询
`edera-server` SHALL 通过 `QueryService` 提供 briefing 数据的查询操作。

#### Scenario: 查询最新 briefing
- **WHEN** 客户端调用 `QueryService.LatestBriefing`
- **THEN** server SHALL 查询数据库返回最新 briefing entity（含 metadata）

#### Scenario: 无 briefing 数据
- **WHEN** 客户端调用 `QueryService.LatestBriefing` 且数据库无记录
- **THEN** server SHALL 返回空结果（briefing=null）

#### Scenario: 列出 briefings
- **WHEN** 客户端调用 `QueryService.ListBriefings(created_from, created_to, limit)`
- **THEN** server SHALL 按时间范围和数量限制查询并返回 briefing 列表

#### Scenario: 获取 briefing 详情
- **WHEN** 客户端调用 `QueryService.GetBriefing(id)`
- **THEN** server SHALL 返回指定 briefing 的完整数据

#### Scenario: briefing 不存在
- **WHEN** 客户端调用 `QueryService.GetBriefing(id)` 且 id 不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

### Requirement: QueryService advice 查询
`edera-server` SHALL 通过 `QueryService` 提供 advice 数据的查询操作。

#### Scenario: 列出 advices
- **WHEN** 客户端调用 `QueryService.ListAdvices(stock_code, direction, created_from, created_to, limit)`
- **THEN** server SHALL 按过滤条件查询并返回 advice 列表

#### Scenario: 获取 advice 详情
- **WHEN** 客户端调用 `QueryService.GetAdvice(id)`
- **THEN** server SHALL 返回 advice 及其关联的 analyses、raw_items、related_events、event_details

#### Scenario: advice 不存在
- **WHEN** 客户端调用 `QueryService.GetAdvice(id)` 且 id 不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

### Requirement: QueryService results 聚合查询
`edera-server` SHALL 通过 `QueryService` 提供 results 页面所需的聚合数据查询。

#### Scenario: 查询 results summary
- **WHEN** 客户端调用 `QueryService.ResultsSummary(stock_code, direction, created_from, created_to)`
- **THEN** server SHALL 返回聚合数据：latest briefing、briefings 列表、advices、events、event_details、summary_items、metadata_bar、failed_sources

### Requirement: QueryService source 健康与日志查询
`edera-server` SHALL 通过 `QueryService` 提供信息源健康状态和执行日志查询。

#### Scenario: 查询 source health
- **WHEN** 客户端调用 `QueryService.SourceHealth`
- **THEN** server SHALL 从 entity store 获取 source 列表，查询数据库返回各 source 的健康摘要和执行日志

#### Scenario: 查询 source logs
- **WHEN** 客户端调用 `QueryService.SourceLogs(source_name, limit)`
- **THEN** server SHALL 返回指定 source（或全部）的执行日志列表

### Requirement: QueryService node output 与 history 查询
`edera-server` SHALL 通过 `QueryService` 提供节点输出和执行历史查询。

#### Scenario: 查询 node outputs
- **WHEN** 客户端调用 `QueryService.NodeOutputs(node_id, run_id, limit)`
- **THEN** server SHALL 返回匹配条件的 node output entity 列表

#### Scenario: 查询 node history
- **WHEN** 客户端调用 `QueryService.NodeHistory(dag_name, node_id, limit)`
- **THEN** server SHALL 返回该节点的历史执行记录（DAG run + node run + outputs）

#### Scenario: DAG 不存在时查询 history
- **WHEN** 客户端调用 `QueryService.NodeHistory` 且 dag_name 不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误
