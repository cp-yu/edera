# dag-run-control Specification (Delta)

## MODIFIED Requirements

### Requirement: 节点重试

系统 SHALL 支持从已结束的 run 中重试一个或多个节点，生成新 cycle_id 并通过 `retry_of` 字段关联原始 run。`node_ids` 为 `string[]` 类型，`cycle_id` 为可选参数。

#### Scenario: Single mode 重试（单节点）

- **WHEN** 用户调用 `POST /api/pipeline/dag/{name}/retry` body `{ "cycle_id": "abc", "node_ids": ["node-3"], "mode": "single" }`
- **THEN** 系统 MUST 创建新 PipelineRun（trigger="retry", retry_of="abc"），从 DB 加载原 cycle 已成功节点的 output，仅重新执行 node-3，run status 仅看 node-3 结果

#### Scenario: Single mode 重试（多节点）

- **WHEN** 用户调用 `POST /api/pipeline/dag/{name}/retry` body `{ "node_ids": ["node-3", "node-4"], "mode": "single" }`
- **THEN** 系统 MUST 创建新 PipelineRun，`retry_nodes = {"node-3", "node-4"}`，按拓扑序执行，内部传播新结果

#### Scenario: Cascade mode 重试（多节点）

- **WHEN** 用户调用 `POST /api/pipeline/dag/{name}/retry` body `{ "node_ids": ["node-3", "node-5"], "mode": "cascade" }`
- **THEN** 系统 MUST 计算 `retry_nodes = downstream(node-3) ∪ downstream(node-5)`，创建新 PipelineRun 并从这些节点开始重新执行

#### Scenario: 重试 input 重建（多节点）

- **WHEN** 系统重试 `[node-3, node-4]` 且 node-3 的上游 node-1、node-2 不在选中集合中
- **THEN** 系统 MUST 从 DB 查询 `NodeOutputEntity WHERE node_id IN (node-1, node-2) AND cycle_id = original`，用 collect 逻辑组装 node-3 的 input payload

#### Scenario: cycle_id 不传时使用默认值

- **WHEN** 用户调用 retry API 未提供 `cycle_id`
- **THEN** 系统 MUST 使用该 DAG 最近一次 `status != 'running'` 的 PipelineRun 的 cycle_id

#### Scenario: 重试原始 run 不存在

- **WHEN** 用户提供的 `cycle_id` 在 DB 中不存在
- **THEN** 系统 MUST 返回 404 错误
