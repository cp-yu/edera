---
capabilities:
  - cap.single-node-loop
---
# single-node-loop Specification

## Purpose
定义 并行循环模式、串行循环模式、循环不破坏 DAG 无环性。
## Requirements
### Requirement: 并行循环模式

系统 SHALL 支持单节点并行循环：同一节点最多同时运行 N 个实例（N 受 `count` 与 resource permits 约束），每个实例接收相同的原始输入。`until` 配置时 SHALL 启用封顶短路：`count` 为迭代总数硬上限（`until` 存在且 `count` 缺省时取系统默认上限），任一实例输出满足 `until` 条件即取消其余未完成实例。

#### Scenario: 固定次数并行循环

- **WHEN** 节点配置 `loop: {mode: parallel, count: 3}`
- **THEN** 系统同时启动 3 个该节点实例，每个实例接收相同输入，产出 3 份独立输出

#### Scenario: 条件停止并行循环（封顶短路）

- **WHEN** 节点配置 `loop: {mode: parallel, count: 5, until: "output.confidence > 0.8"}`，第 2 个完成的实例输出满足条件
- **THEN** 系统取消其余未完成实例并提前收尾，输出 payload 为 `[匹配实例的 payload]`，`metadata.loop_until_matched` 为 true

#### Scenario: until 跑满未命中

- **WHEN** 节点配置 `until` 且全部 `count` 个实例完成后无一满足条件
- **THEN** 系统返回全部成功实例的 payload 列表，`metadata.loop_until_matched` 为 false

#### Scenario: 并行循环部分失败

- **WHEN** 3 个并行实例中 1 个失败
- **THEN** 系统收集成功的 2 个输出传递给下游，失败实例记录到 run metadata

#### Scenario: 输出形状恒为列表

- **WHEN** 并行循环以任意路径收尾（短路命中、跑满、部分失败）
- **THEN** `NodeOutput.payload` MUST 为列表

### Requirement: 串行循环模式

系统 SHALL 支持单节点串行循环：节点反复执行，每次用上一次的输出作为输入，逐步迭代精炼。

#### Scenario: 固定次数串行循环

- **WHEN** 节点配置 `loop: {mode: serial, count: 3}`
- **THEN** 系统执行该节点 3 次，第 1 次用原始输入，第 2 次用第 1 次输出，第 3 次用第 2 次输出

#### Scenario: 条件停止串行循环

- **WHEN** 节点配置 `loop: {mode: serial, until: "output.confidence > 0.8"}`，第 1 次输出 `{confidence: 0.6}`，第 2 次输出 `{confidence: 0.85}`
- **THEN** 系统在第 2 次迭代后停止，返回 `{confidence: 0.85}` 作为最终输出

#### Scenario: 串行循环达到最大次数

- **WHEN** 节点配置 `loop: {mode: serial, until: "output.done == true", count: 10}`，且条件始终不满足
- **THEN** 系统在第 10 次迭代后强制停止，返回最后一次输出

### Requirement: 循环不破坏 DAG 无环性

单节点循环 MUST 是节点级行为，MUST NOT 在 DAG 拓扑中引入环。

#### Scenario: DAG 校验不受循环影响

- **WHEN** DAG 中一个节点配置了 `loop`，DAG Runner 执行拓扑排序
- **THEN** 拓扑排序正常完成，循环节点被视为单个节点处理

#### Scenario: 循环节点的下游等待循环完成

- **WHEN** 一个配置了 `loop` 的节点有下游节点
- **THEN** 下游节点等待循环全部完成后才开始执行

### Requirement: 循环并发控制

配置了 `loop` 与 `resource` 的节点 SHALL 以迭代为 permit 持有单元：每个迭代执行前 acquire 一个 permit，结束（含取消）后 release。Resource Entity 的 `permits` 即最大并发迭代数。循环节点的外壳 MUST NOT 持有 permit。

#### Scenario: permits 限制并发迭代数

- **WHEN** 节点配置 `loop: {mode: parallel, count: 5}` 且 `resource` 指向 `permits: 2` 的 Resource Entity
- **THEN** 同时运行的迭代数 MUST 不超过 2，5 个迭代全部完成

#### Scenario: permits 为 1 不死锁

- **WHEN** 并行循环节点的 resource `permits: 1`
- **THEN** 迭代逐个串行执行直至收尾，MUST NOT 死锁

#### Scenario: 与非循环节点共享 resource

- **WHEN** 循环节点与普通节点声明同一 resource
- **THEN** 循环迭代与普通节点在同一 permit 池公平排队，互斥语义不变

#### Scenario: 串行循环迭代持锁

- **WHEN** 串行循环节点配置 `resource`
- **THEN** 每个迭代执行前 acquire、结束后 release，跨 DAG 共享该 resource 的持有者参与排队

#### Scenario: 无 resource 时不限并发

- **WHEN** 循环节点未配置 `resource`
- **THEN** 并行模式一次性启动 `count` 个迭代，行为与现状一致

### Requirement: 循环配置序列化往返保真

`loop` 与 `resource` SHALL 作为节点实例顶层字段在 graph API 全链路往返保真：`GET /api/graph/dag/{name}` 输出两字段，`PUT /api/graph/dag/{name}` 原样持久化，MUST NOT 静默丢弃。

#### Scenario: GET 返回 loop 与 resource

- **WHEN** DAG 节点实例配置了 `loop` 与 `resource`，调用 `GET /api/graph/dag/{name}`
- **THEN** 返回的节点 item MUST 包含 `loop: {mode, count, until}` 与 `resource` 字段

#### Scenario: PUT 往返保真

- **WHEN** 客户端将 GET 返回的 nodes 原样 PUT 回去
- **THEN** 持久化后的 DAG 配置中 `loop` 与 `resource` MUST 与 PUT 前一致

#### Scenario: 非法 loop 配置被拒

- **WHEN** PUT 的节点 `loop.mode` 不在 `parallel|serial`，或 `count < 1`
- **THEN** 系统 MUST 返回 400 错误，不持久化

