## MODIFIED Requirements

### Requirement: QueryService source 健康与日志查询
`edera-server` SHALL 通过 `QueryService` 提供信息源健康状态和执行日志查询。Source 列表 SHALL 从 DB-backed Entity Store 查询，MUST NOT 依赖 `RuntimeControlSnapshot` 中的全量 EntityStore mirror。

#### Scenario: 查询 source health
- **WHEN** 客户端调用 `QueryService.SourceHealth`
- **THEN** server SHALL 从 DB-backed entity store 获取 source 列表，查询数据库返回各 source 的健康摘要和执行日志

#### Scenario: 查询 source logs
- **WHEN** 客户端调用 `QueryService.SourceLogs(source_name, limit)`
- **THEN** server SHALL 返回指定 source（或全部）的执行日志列表

### Requirement: QueryService node output 与 history 查询
`edera-server` SHALL 通过 `QueryService` 提供节点输出和执行历史查询。DAG existence validation SHALL use DB-backed DAG repository or persisted run facts, MUST NOT use `runtime_snapshot().config.dags`.

#### Scenario: 查询 node outputs
- **WHEN** 客户端调用 `QueryService.NodeOutputs(node_id, run_id, limit)`
- **THEN** server SHALL 返回匹配条件的 node output entity 列表

#### Scenario: 查询 node history
- **WHEN** 客户端调用 `QueryService.NodeHistory(dag_name, node_id, limit)`
- **THEN** server SHALL 返回该节点的历史执行记录（DAG run + node run + outputs）

#### Scenario: DAG 不存在时查询 history
- **WHEN** 客户端调用 `QueryService.NodeHistory` 且 dag_name 在 DB-backed DAG repository 和历史 DagRun 中均不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误
