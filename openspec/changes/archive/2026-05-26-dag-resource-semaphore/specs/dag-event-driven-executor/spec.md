## MODIFIED Requirements

### Requirement: Event-driven dispatcher 调度

系统 SHALL 使用中央 dispatcher + `asyncio.Queue` 调度 DAG 节点执行。节点完成后 MUST 立即向 queue 发送完成事件，dispatcher 消费事件后评估下游节点就绪条件并启动就绪节点。对声明了 `resource` 的节点，dispatcher MUST 在就绪条件满足后额外执行 semaphore acquire gate，acquire 失败则暂缓启动。

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
