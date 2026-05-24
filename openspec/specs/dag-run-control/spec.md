# dag-run-control Specification

## Purpose
此规约记录变更 dag-observability-controllability 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Soft stop

系统 SHALL 支持 soft stop：通过 `asyncio.Event` 通知 dispatcher 停止调度新节点，等待所有当前正在执行的节点完成后终止 DAG 运行。

#### Scenario: Soft stop 不中断当前节点

- **WHEN** 用户触发 soft stop 且有节点正在执行
- **THEN** 系统 MUST 等待当前正在执行的节点完成，MUST NOT 启动新节点，完成后将 run 标记为 `cancelled`

#### Scenario: Soft stop 无运行中节点

- **WHEN** 用户触发 soft stop 且 dispatcher 处于等待 queue 状态（无节点在执行）
- **THEN** 系统 MUST 立即终止 dispatcher 循环并返回当前结果

### Requirement: Hard stop

系统 SHALL 支持 hard stop：通过 `task.cancel()` 立即取消 DAG 运行 task，中断所有正在执行的节点。

#### Scenario: Hard stop 立即中断

- **WHEN** 用户触发 hard stop（`force: true`）
- **THEN** 系统 MUST 立即 cancel DAG 运行 task，`CancelledError` 终止 dispatcher，run 标记为 `cancelled`

### Requirement: Stop API 参数扩展

系统 SHALL 在 `POST /api/pipeline/dag/{dag_name}/stop` 接受 `force` 参数，默认 false（soft stop），true 时执行 hard stop。

#### Scenario: 默认 soft stop

- **WHEN** 用户调用 `POST /api/pipeline/dag/{name}/stop` 无 body 或 `{ "force": false }`
- **THEN** 系统 MUST 执行 soft stop

#### Scenario: Force hard stop

- **WHEN** 用户调用 `POST /api/pipeline/dag/{name}/stop` body `{ "force": true }`
- **THEN** 系统 MUST 执行 hard stop

### Requirement: 节点重试

系统 SHALL 支持从已结束的 run 中重试失败节点，生成新 cycle_id 并通过 `retry_of` 字段关联原始 run。

#### Scenario: Single mode 重试

- **WHEN** 用户调用 `POST /api/pipeline/dag/{name}/retry` body `{ "cycle_id": "abc", "node_id": "node-3", "mode": "single" }`
- **THEN** 系统 MUST 创建新 PipelineRun（trigger="retry", retry_of="abc"），从 DB 加载原 cycle 已成功节点的 output，仅重新执行 node-3，run status 仅看 node-3 结果

#### Scenario: Cascade mode 重试

- **WHEN** 用户调用 `POST /api/pipeline/dag/{name}/retry` body `{ "cycle_id": "abc", "node_id": "node-3", "mode": "cascade" }`
- **THEN** 系统 MUST 创建新 PipelineRun（trigger="retry", retry_of="abc"），从 DB 加载原 cycle 已成功节点的 output（排除 node-3 及其下游），从 node-3 开始重新执行所有下游节点

#### Scenario: 重试 input 重建

- **WHEN** 系统重试 node-3 且 node-3 的上游为 node-1 和 node-2
- **THEN** 系统 MUST 从 DB 查询 `NodeOutputEntity WHERE node_id IN (node-1, node-2) AND cycle_id = original`，用 collect 逻辑组装 node-3 的 input payload

#### Scenario: 重试原始 run 不存在

- **WHEN** 用户提供的 `cycle_id` 在 DB 中不存在
- **THEN** 系统 MUST 返回 404 错误

### Requirement: PipelineRun retry 关联

系统 SHALL 在 `PipelineRun` 表增加 `retry_of` 字段（nullable），指向被重试的原始 cycle_id。trigger 值 MUST 为 `"retry"`。

#### Scenario: Retry run 记录关联

- **WHEN** 系统创建 retry run
- **THEN** PipelineRun 记录 MUST 包含 `retry_of` 指向原始 cycle_id，`trigger` 为 `"retry"`

#### Scenario: 查询 retry 链

- **WHEN** 查询某次 run 的所有 retry
- **THEN** 系统 MUST 能通过 `retry_of` 字段递归追溯完整 retry 链

