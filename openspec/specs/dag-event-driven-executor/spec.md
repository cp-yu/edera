# dag-event-driven-executor Specification

## Purpose
此规约记录变更 dag-observability-controllability 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
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

### Requirement: Fan-in barrier 模式

系统 SHALL 支持 barrier fan-in 模式：目标节点等待所有上游节点完成后，收集所有上游 output 一次性作为 input 启动执行。barrier MUST 为默认 fan-in 模式。

#### Scenario: Barrier 等待所有上游完成

- **WHEN** node-C 配置 `fan_in_mode: "barrier"` 且有上游 node-A 和 node-B
- **THEN** dispatcher MUST 在 node-A 和 node-B 都完成后才启动 node-C，node-C 的 input 为两者 output 的 collect

#### Scenario: 未配置 fan_in_mode 时默认 barrier

- **WHEN** 多上游节点的目标节点未显式配置 `fan_in_mode`
- **THEN** 系统 MUST 按 barrier 模式处理

### Requirement: Fan-in accumulate 模式

系统 SHALL 支持 accumulate fan-in 模式：每个上游完成时立即 spawn 一个 sub-task 并行处理该 output，所有 sub-task 完成后 collect 结果发给下游。

#### Scenario: Accumulate 逐个处理上游结果

- **WHEN** node-C 配置 `fan_in_mode: "accumulate"` 且上游 node-A 先完成
- **THEN** dispatcher MUST 立即 spawn node-C 的 sub-task 处理 node-A 的 output，不等待 node-B

#### Scenario: Accumulate sub-task 并行执行

- **WHEN** node-A 和 node-B 先后完成，node-C 为 accumulate 模式
- **THEN** node-C 的两个 sub-task MUST 并行执行

#### Scenario: Accumulate 完成后合并发给下游

- **WHEN** node-C 的所有 sub-task 完成
- **THEN** dispatcher MUST collect 所有 sub-task 结果，作为 node-C 的最终 output 发给下游 node-D

### Requirement: 错误路径隔离
系统 SHALL 在节点失败时仅阻断该节点的 required 下游路径，MUST NOT 影响独立路径上的节点执行。Optional 边的上游失败 SHALL NOT 阻塞下游，且 MUST NOT 向下游 payload 注入失败占位。

#### Scenario: 失败节点阻断下游
- **WHEN** node-C 执行失败且 node-D 仅通过 required 边依赖 node-C
- **THEN** node-D MUST NOT 被启动，且 node-D 的 `node_runs` SHALL 记录 `status=failed`、`failure_kind=upstream_failed`

#### Scenario: 独立路径不受影响
- **WHEN** node-C 执行失败，但 node-E 位于独立路径（不依赖 node-C）
- **THEN** node-E MUST 正常执行

#### Scenario: Optional 节点失败视为入边失败事实
- **WHEN** 标记为 `optional: true` 的节点执行失败
- **THEN** dispatcher MUST 将其 optional 出边记录为 failed edge input facts，并 SHALL 正常评估下游节点，不得向下游 payload 注入 `None`

### Requirement: DAG 执行结果

系统 SHALL 在所有可达节点执行完毕（或因上游失败而不可达）后返回 `DagRunResult`，包含所有节点的 output、failures 和 warnings。

#### Scenario: 正常完成返回结果

- **WHEN** DAG 中所有可达节点执行完毕
- **THEN** dispatcher MUST 返回 `DagRunResult`，`node_outputs` 包含所有已执行节点的 output，`failures` 包含所有失败节点的错误信息

#### Scenario: 部分路径失败的结果

- **WHEN** DAG 中某路径失败但其他路径成功
- **THEN** `DagRunResult.ok` MUST 为 true（只要有成功的 sink 节点），`failures` 记录失败节点

### Requirement: Fan-in barrier 增加 edge optional 判定
系统 SHALL 在 fan-in barrier 模式中区分 optional 和 required 边。当所有 required 边的上游完成（或所有入边均为 optional）时，下游节点 SHALL 开始执行。Optional 边的上游失败 SHALL NOT 阻塞下游，并且 SHALL 通过 runtime facts/context 记录。

#### Scenario: Required 边全部完成触发执行
- **WHEN** node-C 有入边 A→C（required）和 B→C（optional），且 A 完成
- **THEN** dispatcher SHALL 在调度 node-C 前写入 A→C 和 B→C 的 edge input facts，并启动 node-C

#### Scenario: Optional 边上游失败不阻塞
- **WHEN** node-C 有入边 A→C（optional）和 B→C（required），A 失败，B 成功
- **THEN** dispatcher SHALL 启动 node-C，node-C 的 payload SHALL 只包含 B 的输出，且 A→C SHALL 记录为 failed edge input

#### Scenario: 所有 required 边上游失败阻塞下游
- **WHEN** node-C 有入边 A→C（required），且 A 失败
- **THEN** node-C SHALL 被标记为 `status=failed`、`failure_kind=upstream_failed`，不执行，并写入 node-C 的所有直接入边 edge input facts

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

### Requirement: Dispatcher 支持 wait 节点挂起
中央 dispatcher SHALL 将 wait 节点作为常规 `asyncio.Task` 调度。当 wait 节点 Task 因等待外部输入而长时间不返回时，dispatcher MUST 通过 `asyncio.wait(FIRST_COMPLETED)` 继续处理其它已完成 Task，不得因 wait 节点挂起而阻塞主循环或独立路径。

#### Scenario: wait 节点挂起不阻塞主循环
- **WHEN** wait 节点 `gate` 的 Task 处于挂起（`waiting`）状态，其它节点 `worker` 正在执行
- **THEN** dispatcher SHALL 在 `worker` 完成时正常消费其完成事件并推进下游，不等待 `gate`

#### Scenario: wait 节点唤醒后正常汇入调度
- **WHEN** 挂起的 wait 节点 `gate` 被唤醒并返回 output
- **THEN** dispatcher SHALL 像处理普通节点完成一样消费 `gate` 完成事件并评估其下游就绪条件

#### Scenario: stop 时取消挂起的 wait 节点
- **WHEN** DAG run 收到 stop（`stop_event` 置位）且存在挂起的 wait 节点
- **THEN** 系统 SHALL 解除该 wait 节点挂起并按 run 既有 stop 路径终止

