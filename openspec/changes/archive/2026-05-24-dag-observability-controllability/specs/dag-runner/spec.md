## MODIFIED Requirements

### Requirement: 拓扑排序与并发调度

系统 SHALL 对 DAG 进行拓扑排序用于环检测和可视化。执行调度 MUST 由 event-driven dispatcher 驱动（节点完成即触发下游），MUST NOT 使用 layer-by-layer 同步循环。`topological_layers()` 保留用于静态校验，不再作为执行调度依据。

#### Scenario: 环检测保留

- **WHEN** DAG Runner 加载 DAG 配置
- **THEN** 系统 MUST 执行拓扑排序验证无环，有环时拒绝加载

#### Scenario: 执行不按层同步

- **WHEN** node-A 完成且 node-B 仅依赖 node-A，但同层 node-C 尚未完成
- **THEN** 系统 MUST 立即启动 node-B，MUST NOT 等待 node-C 完成

### Requirement: 数据路由

系统 SHALL 将上游节点的输出通过 dispatcher 事件机制路由到下游节点的输入。路由时 MUST 考虑 edge 条件表达式和目标节点的 `fan_in_mode`。

#### Scenario: 正常数据路由

- **WHEN** 节点完成执行且出边无条件
- **THEN** dispatcher MUST 将完成事件传播到所有下游节点

#### Scenario: 条件路由

- **WHEN** 节点输出 `{sentiment: "negative"}`，出边条件为 `"output.sentiment == 'negative'"`
- **THEN** dispatcher MUST 仅将完成事件传播到条件为 true 的边的目标节点

#### Scenario: fan_in_mode barrier 路由

- **WHEN** 下游节点配置 `fan_in_mode: "barrier"`（或未配置，默认 barrier）
- **THEN** dispatcher MUST 等待所有上游完成后，收集可用结果一次性传给下游

#### Scenario: fan_in_mode accumulate 路由

- **WHEN** 下游节点配置 `fan_in_mode: "accumulate"`
- **THEN** dispatcher MUST 在每个上游完成时立即 spawn sub-task 处理该 output

### Requirement: Fan-out/Fan-in

系统 SHALL 支持 fan-out（一个节点的输出拆分到多个并发节点）和 fan-in（多个节点的输出汇聚）。Fan-in MUST 支持 barrier 和 accumulate 两种模式，配置在目标节点的 `fan_in_mode` 字段上。

#### Scenario: Fan-out 拆分到并发执行

- **WHEN** 上游节点输出 10 条 Entity，出边标记 `fan_out: true`
- **THEN** dispatcher MUST 将 10 条 Entity 拆分为 10 个独立的下游节点实例并发执行

#### Scenario: Fan-in barrier 模式汇聚

- **WHEN** 10 个并发节点完成，其中 8 个成功、2 个失败，目标节点 `fan_in_mode: "barrier"`
- **THEN** dispatcher MUST 等待全部完成后，汇聚 8 条成功结果传给下游，失败的 2 条记录到 run metadata

#### Scenario: Fan-in accumulate 模式逐个处理

- **WHEN** 10 个并发节点逐个完成，目标节点 `fan_in_mode: "accumulate"`
- **THEN** 每个节点完成时 dispatcher MUST 立即 spawn sub-task 处理其 output，全部 sub-task 完成后 collect 结果发给下游

### Requirement: 单节点失败不阻塞管道

系统 SHALL 在单个节点执行失败时仅阻断该节点的下游路径，MUST NOT 影响独立路径上的节点执行。optional 节点失败 MUST 视为完成（payload=None），正常触发下游。

#### Scenario: 单个节点失败仅阻断下游路径

- **WHEN** node-C 执行失败
- **THEN** node-C 的下游 MUST NOT 被启动，但与 node-C 无依赖关系的独立路径 MUST 正常执行

#### Scenario: optional 节点失败视为完成

- **WHEN** 一个标记为 `optional: true` 的节点执行失败
- **THEN** dispatcher MUST 将其视为完成（payload=None），正常触发下游节点的就绪条件评估
