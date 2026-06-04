## ADDED Requirements

### Requirement: BFF node execution logs API
`edera-web` SHALL 通过纯 gRPC client 暴露节点 execution logs 查询 HTTP API。该 API MUST 支持按 `run_id` 和 `node_id` 过滤，并 MUST NOT 读取本地 repository、config 目录或 `DagController`。

#### Scenario: HTTP logs route uses gRPC
- **WHEN** 浏览器请求节点 execution logs HTTP route
- **THEN** BFF SHALL 通过 `GrpcClient` 调用 `edera-server` 的查询 RPC
- **AND** BFF SHALL 将返回 JSON 透传给浏览器

#### Scenario: Logs query filters by run and node
- **WHEN** 浏览器请求某个 `run_id` 与 `node_id` 的 execution logs
- **THEN** BFF SHALL 将 `run_id` 和 `node_id` 传递给 gRPC 查询
- **AND** 响应 SHALL 只包含该节点在该 run 下的日志索引或日志内容

#### Scenario: Node outputs route remains output-only
- **WHEN** 浏览器请求 `/api/node-outputs`
- **THEN** BFF SHALL 继续只返回业务 output entities
- **AND** BFF MUST NOT 将 execution logs 混入 output entities 响应
