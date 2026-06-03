---
capabilities:
  - cap.operations.dag-node-wait-input
---
# dag-node-wait-input Specification

## Purpose
定义 Wait 节点类型、Waiting 运行状态、信号先到即直接通过、信号后到唤醒挂起节点等能力。
## Requirements
### Requirement: Wait 节点类型
系统 SHALL 在 `NodeConfig` discriminated union 中提供 `type: "wait"` variant，作为 DAG 拓扑层显式的等待停顿点。`WaitNodeConfig` MUST 包含 `wait_for`（布尔表达式字符串）字段，MUST 支持可选 `timeout_seconds`（> 0）和 `consume`（默认 `true`）字段。

#### Scenario: 声明 wait 节点
- **WHEN** DAG 配置中存在 `{type: "wait", wait_for: "event:approve:abc", name: "gate"}` 的节点
- **THEN** 系统 SHALL 将其解析为 `WaitNodeConfig`，并作为独立 DAG 顶点参与拓扑排序

#### Scenario: wait_for 不可为空
- **WHEN** wait 节点的 `wait_for` 为空字符串
- **THEN** 系统 SHALL 拒绝该配置并报校验错误

### Requirement: Waiting 运行状态
系统 SHALL 在 `node_runs.status` 取值集中新增 `waiting`，与 `running`/`succeeded`/`failed` 等并列。wait 节点挂起等待外部输入期间 MUST 记录为 `waiting`，被唤醒后 MUST 转回 `running` 再产出结果。

#### Scenario: 挂起期间状态为 waiting
- **WHEN** wait 节点求值 `wait_for` 未满足而挂起
- **THEN** 系统 SHALL 将该节点 `node_runs.status` 记录为 `waiting`

#### Scenario: 唤醒后状态流转
- **WHEN** 处于 `waiting` 的 wait 节点收到满足信号
- **THEN** 系统 SHALL 将其状态转为 `running`，产出 payload 后转为 `succeeded`

### Requirement: 信号先到即直接通过
wait 节点执行时 SHALL 先求值一次 `wait_for`。当对应 bit 已置位（信号先于节点到达），系统 MUST 立即取最近的 emit payload 并返回，不进入 `waiting` 状态。

#### Scenario: 信号先到
- **WHEN** `event:approve:abc` 已在 `event_group_bits` 置位，随后 wait 节点 `gate`（`wait_for: "event:approve:abc"`）开始执行
- **THEN** 系统 SHALL 立即从 `emit_records` 取该事件最近 payload 作为节点 output 返回，节点状态不经过 `waiting`

### Requirement: 信号后到唤醒挂起节点
当 wait 节点已挂起为 `waiting`，后续 `EventService.Emit` 置位匹配 bit 时，系统 MUST 重新求值该节点的 `wait_for` 表达式并以 emit payload 唤醒它。

#### Scenario: 信号后到唤醒
- **WHEN** wait 节点 `gate` 已挂起等待 `event:approve:abc`，随后客户端 `emit("event:approve:abc", payload={"ok": true})`
- **THEN** 系统 SHALL 唤醒 `gate`，其 output payload SHALL 为 `{"ok": true}`

#### Scenario: 不匹配信号不唤醒
- **WHEN** wait 节点 `gate` 等待 `event:approve:abc`，但 emit 的是 `event:approve:xyz`
- **THEN** 系统 SHALL NOT 唤醒 `gate`，`gate` 保持 `waiting`

### Requirement: 超时按失败处理
当 wait 节点声明 `timeout_seconds` 且在该时长内未被唤醒，系统 MUST 将其标记为 `failed`、`failure_kind = "wait_timeout"`，并按既有失败传播语义处理下游。

#### Scenario: 等待超时
- **WHEN** wait 节点 `gate` 声明 `timeout_seconds: 5` 且 5 秒内无匹配信号
- **THEN** 系统 SHALL 将 `gate` 标记为 `status=failed`、`failure_kind=wait_timeout`

### Requirement: consume 控制信号生命周期
当 `consume = true`（默认），wait 节点被唤醒后系统 MUST consume（清除）匹配的 bit，使信号为一次性。当 `consume = false`，系统 MUST 保留 bit，使信号为持久水位。

#### Scenario: 一次性信号
- **WHEN** `consume: true` 的 wait 节点被 `event:approve:abc` 唤醒
- **THEN** 系统 SHALL 清除 `event:approve:abc` bit

#### Scenario: 水位信号
- **WHEN** `consume: false` 的 wait 节点被 `event:market-open` 唤醒
- **THEN** 系统 SHALL 保留 `event:market-open` bit

### Requirement: Run 隔离靠信号命名
系统 SHALL 通过 `wait_for` 表达式中的信号命名实现 run 隔离与全局广播，不引入独立投递机制。带 `<run_id>` 的信号名 MUST 仅唤醒该 run 内的等待节点；不带 run 标识的信号名 MUST 对所有匹配等待者求值。

#### Scenario: run 隔离不串台
- **WHEN** run A 的 wait 节点等待 `event:approve:A`，run B 的 wait 节点等待 `event:approve:B`，客户端 `emit("event:approve:A")`
- **THEN** 系统 SHALL 仅唤醒 run A 的等待节点，run B 保持 `waiting`

### Requirement: 挂起不阻塞独立路径
wait 节点挂起为 `waiting` 期间 MUST NOT 阻塞 DAG 中不依赖它的独立路径节点执行。

#### Scenario: 独立路径继续执行
- **WHEN** wait 节点 `gate` 挂起，节点 `independent` 位于不依赖 `gate` 的独立路径
- **THEN** dispatcher SHALL 正常执行 `independent`，不受 `gate` 挂起影响

### Requirement: 重启重放恢复等待
系统 SHALL 通过现有 retry/resume 重放机制恢复中断的等待，不引入额外持久化表。重启后重放到 wait 节点时 MUST 重新求值 `wait_for`：bit 已置位则直接通过，否则重新挂起。

#### Scenario: 重启后 bit 仍置位则续行
- **WHEN** wait 节点 `gate` 等待 `event:approve:abc` 期间服务器重启，且重启前 `event:approve:abc` 已置位并保留于 `event_group_bits`
- **THEN** retry/resume 重放到 `gate` 时系统 SHALL 求值命中并直接通过

#### Scenario: 重启后 bit 未置位则重新挂起
- **WHEN** wait 节点 `gate` 等待期间重启，且 `event:approve:abc` 从未置位
- **THEN** retry/resume 重放到 `gate` 时系统 SHALL 重新进入 `waiting`

### Requirement: Waiting 状态实时可观测
系统 SHALL 在 wait 节点进入 `waiting` 时通过 `event_bus` 发布 `node.waiting` 事件，复用现有 SSE 通道推送至 Web Console，事件 MUST 携带 `run_id`、节点名与 `wait_for` 表达式。

#### Scenario: waiting 经 SSE 推送
- **WHEN** wait 节点 `gate` 进入 `waiting`
- **THEN** 系统 SHALL 通过 `event_bus.publish("node.waiting", run_id=..., node=..., wait_for=...)` 推送，订阅方可实时获知该节点正在等待
