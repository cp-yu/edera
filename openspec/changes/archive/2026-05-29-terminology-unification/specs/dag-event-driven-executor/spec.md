## MODIFIED Requirements

### Requirement: Event-driven dispatcher 调度
系统 SHALL 使用中央 dispatcher + `asyncio.Queue` 调度 DAG 节点执行。节点完成后 MUST 立即向 queue 发送完成事件，dispatcher 消费事件后评估下游节点就绪条件并启动就绪节点。对声明了 `resource` 的节点，dispatcher MUST 在就绪条件满足后额外执行 semaphore acquire gate，acquire 失败则暂缓启动。所有涉及 `cycle_id` 的代码改为 `run_id`。

#### Scenario: 节点完成立即触发下游
- **WHEN** node-A 完成执行且 node-B 仅依赖 node-A
- **THEN** dispatcher MUST 在消费 node-A 完成事件后立即启动 node-B，不等待同层其他节点

#### Scenario: 无依赖的起始节点并发启动
- **WHEN** DAG 中有多个无上游依赖的节点
- **THEN** dispatcher MUST 在初始化时并发启动所有起始节点

#### Scenario: Dispatcher 消费完成事件
- **WHEN** 节点 task 完成并向 queue 发送 `(node_id, output)` 事件
- **THEN** dispatcher MUST 更新该节点状态、评估所有下游节点的就绪条件、对满足条件的下游节点执行 semaphore gate（若有 resource 声明）后调用 `asyncio.create_task`

#### Scenario: Resource 节点完成触发 pending 重评估
- **WHEN** 声明了 resource 的节点完成执行并 release semaphore
- **THEN** dispatcher MUST 重新评估所有因 semaphore 不可用而暂缓的 pending 节点

## ADDED Requirements

### Requirement: Edge input facts 使用 run_id
系统 SHALL 在目标节点调度决策点生成所有直接入边 facts，记录到 `edge_inputs` 表。所有 edge input facts MUST 使用 `run_id` 关联到对应的 DAG run。

#### Scenario: 记录 edge input fact 使用 run_id
- **WHEN** dispatcher 在节点调度决策点生成边输入事实
- **THEN** 系统 SHALL 创建 EdgeInput 记录，`run_id` 字段关联到当前 DAG run

#### Scenario: 查询 edge inputs 使用 run_id
- **WHEN** 系统查询特定 run 的边输入事实
- **THEN** 系统 SHALL 通过 `run_id` 字段过滤（如 `WHERE run_id = 'abc123'`）

### Requirement: Node failure_kind 区分使用 run_id
系统 SHALL 使用 `node_runs.failure_kind` 字段区分执行失败（`execution_failed`）和上游失败（`upstream_failed`）。所有 node_runs 记录 MUST 使用 `run_id` 关联到对应的 DAG run。

#### Scenario: 执行失败标记
- **WHEN** 节点自身执行抛出异常
- **THEN** 系统 SHALL 设置 `failure_kind = "execution_failed"`，`run_id` 关联到当前 DAG run

#### Scenario: 上游失败标记
- **WHEN** 节点因上游节点失败而跳过执行
- **THEN** 系统 SHALL 设置 `failure_kind = "upstream_failed"`，`run_id` 关联到当前 DAG run
