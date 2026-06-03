---
capabilities:
  - cap.operations.multi-node-retry
---
# multi-node-retry Specification

## Purpose
定义 多节点 retry API、run_id 可选化、响应包含实际执行节点集合、single 模式内部拓扑传播等能力。
## Requirements
### Requirement: 多节点 retry API

系统 SHALL 在 `POST /api/dags/{dag_name}/retry` 接受 `node_ids: string[]` 参数，替代原 `node_id` 单值参数。

#### Scenario: 多节点 single mode 重试

- **WHEN** 用户调用 `POST /api/dags/{name}/retry` body `{ "node_ids": ["node-3", "node-4"], "mode": "single" }`
- **THEN** 系统 MUST 创建新 DagRun（source="retry"），`retry_nodes = set(node_ids)`，从 DB 加载原 run 中非 retry_nodes 的 output 作为 prefilled，按拓扑序执行选中节点集合

#### Scenario: 多节点 cascade mode 重试

- **WHEN** 用户调用 `POST /api/dags/{name}/retry` body `{ "node_ids": ["node-3", "node-5"], "mode": "cascade" }`
- **THEN** 系统 MUST 计算 `retry_nodes = ∪ downstream(node_i)`，创建新 DagRun 并执行

#### Scenario: node_ids 中包含无效节点

- **WHEN** 用户提供的 `node_ids` 中包含不存在于 DAG 中的节点 ID
- **THEN** 系统 MUST 返回 400 错误，指明无效的节点 ID

### Requirement: run_id 可选化

系统 SHALL 将 `run_id` 参数设为可选，不传时默认取该 DAG 最近一次非 running 状态的 DagRun。

#### Scenario: 不传 run_id 使用默认值

- **WHEN** 用户调用 retry API 未提供 `run_id`
- **THEN** 系统 MUST 查询该 DAG 最近一次 `status != 'running'` 的 DagRun 作为数据来源

#### Scenario: 无可用历史 run

- **WHEN** 用户调用 retry API 未提供 `run_id` 且该 DAG 无任何已结束的 run
- **THEN** 系统 MUST 返回 404 错误

### Requirement: 响应包含实际执行节点集合

系统 SHALL 在 retry API 响应中返回 `retry_nodes` 字段，包含实际将被执行的完整节点 ID 列表。

#### Scenario: 响应结构

- **WHEN** retry 请求成功
- **THEN** 响应 MUST 包含 `{ "run_id", "retry_of", "node_ids", "mode", "retry_nodes" }`，其中 `retry_nodes` 为实际执行的节点集合

### Requirement: single 模式内部拓扑传播

在 single 模式下，选中节点集合内部 MUST 按拓扑序执行，内部节点间传播新结果，外部输入使用 prefilled 数据。

#### Scenario: 连续选中节点间传播新结果

- **WHEN** 用户选中 `[node-3, node-4]` 且 DAG 中 `node-3 → node-4`
- **THEN** node-3 MUST 使用 prefilled 中其上游的 output 作为 input，node-4 MUST 使用 node-3 的新 output 作为 input

#### Scenario: 不连通选中节点并行执行

- **WHEN** 用户选中 `[node-2, node-6]` 且两者在 DAG 中无依赖关系
- **THEN** 系统 MUST 并行执行 node-2 和 node-6，各自使用 prefilled 中其上游的 output

### Requirement: prefilled 数据完整性校验

系统 SHALL 在执行重试前校验所需的 prefilled 数据是否完整。

#### Scenario: 上游节点无可用 output

- **WHEN** 选中节点的上游（不在选中集合中）在指定 run 中没有成功的 output 记录
- **THEN** 系统 MUST 返回 400 错误，说明缺失的上游节点

### Requirement: 前端多选重试交互

前端 SHALL 支持框选和 Ctrl+点击多选节点后，通过右键菜单触发批量重试。

#### Scenario: 多选后右键菜单

- **WHEN** 用户多选了 N 个节点并在选中集合内的节点上右键
- **THEN** 系统 MUST 显示"重试 N 个节点"和"重试 N 个节点及下游"菜单项

#### Scenario: 右键点在选中集合外

- **WHEN** 用户多选了节点后在选中集合外的节点上右键
- **THEN** 系统 MUST 清除多选状态，切换为该节点的单节点上下文菜单

#### Scenario: 无可用 run 时菜单置灰

- **WHEN** 用户多选节点后右键，但该 DAG 无可用的已结束 run
- **THEN** 重试菜单项 MUST 置灰（disabled），hover 时显示 tooltip："找不到可用的 prefill 的 node"

#### Scenario: 触发后清除选中态

- **WHEN** 用户通过菜单触发批量重试
- **THEN** 系统 MUST 立即清除节点选中状态，并用 API 返回的 `retry_nodes` 驱动"重试中"视觉高亮
