---
capabilities:
  - cap.single-node-loop
---
# single-node-loop Specification

## Purpose
定义 并行循环模式、串行循环模式、循环不破坏 DAG 无环性。
## Requirements
### Requirement: 并行循环模式

系统 SHALL 支持单节点并行循环：同一节点同时启动 N 个实例，每个实例接收相同的原始输入。

#### Scenario: 固定次数并行循环

- **WHEN** 节点配置 `loop: {mode: parallel, count: 3}`
- **THEN** 系统同时启动 3 个该节点实例，每个实例接收相同输入，产出 3 份独立输出

#### Scenario: 条件停止并行循环

- **WHEN** 节点配置 `loop: {mode: parallel, until: "output.confidence > 0.8"}`
- **THEN** 系统持续启动新实例，直到任一实例输出满足条件后停止

#### Scenario: 并行循环部分失败

- **WHEN** 3 个并行实例中 1 个失败
- **THEN** 系统收集成功的 2 个输出传递给下游，失败实例记录到 run metadata

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
