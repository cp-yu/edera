---
capabilities:
  - cap.core.event-emit-rpc
---
# event-emit-rpc Specification

## Purpose
定义 EventService.Emit RPC、emit 记录持久化、emit 路径统一等能力。
## Requirements
### Requirement: EventService.Emit RPC

系统 SHALL 在 `EventService` 中提供 `Emit(EmitRequest) returns (JsonResponse)` RPC，作为唯一外部事件注入入口。`EmitRequest` MUST 包含 `event` 字段（事件名）和 `payload_json` 字段（可选 payload）。

#### Scenario: 注入普通事件

- **WHEN** 客户端调用 `EventService.Emit({event: "event:website-updated", payload_json: "{\"url\":\"https://...\"}"})`
- **THEN** 系统置位 `event:website-updated` bit，并将 payload 写入 emit 记录表

#### Scenario: 注入 clear 事件

- **WHEN** 客户端调用 `EventService.Emit({event: "clear:event:market-open"})`
- **THEN** 系统复位 `event:market-open` bit

#### Scenario: 注入 manual 事件

- **WHEN** 客户端调用 `EventService.Emit({event: "manual:dag:default"})`
- **THEN** 系统直接 fire `dag:default`，绕过 wait_for 匹配

### Requirement: emit 记录持久化

系统 SHALL 将每次 emit 调用记录到 `emit_records` 表，包含事件名、payload、调用时间、来源标识、深度。

#### Scenario: 记录 emit 历史

- **WHEN** 任意来源调用 emit
- **THEN** 系统在 `emit_records` 表插入一条记录

#### Scenario: target DAG 通过 runtime context 查询 payload

- **WHEN** trigger fire 后 DAG run 启动，DAG 内 source node 需要读取最近的 emit payload
- **THEN** node 通过 runtime context 查询 `emit_records` 中该事件的最近一条记录

### Requirement: emit 路径统一

系统 SHALL 让所有 DAG/Node 触发都经过 emit 路径，包括手动触发、定时触发、事件触发。

#### Scenario: 手动运行 DAG 走 emit

- **WHEN** 用户在 Web Console 点击"运行"按钮触发 `dag:default`
- **THEN** 系统调用 `emit("manual:dag:default", payload={inputs: ...})`

#### Scenario: cron emitter 走 emit

- **WHEN** cron tick 到达
- **THEN** cron emitter 调用 `emit("cron:\"...\"")`，与外部 emit 走同一路径

### Requirement: emit 驱动 WaitRegistry 求值
`TriggerExecutor.emit()` 在置位 bit 后，除遍历 trigger 反向索引外，MUST 额外重新求值 `WaitRegistry` 中所有挂起等待者的 `wait_for` 表达式。表达式被满足的等待者 SHALL 以最近的 emit payload 被唤醒（`Future.set_result`）。WaitRegistry 是 run 内挂起 wait 节点的唤醒入口，与启动新 run 的 `fire()` 路径并列。

#### Scenario: emit 唤醒挂起等待者
- **WHEN** WaitRegistry 中存在等待 `event:approve:abc` 的挂起节点，客户端 `emit("event:approve:abc", payload)`
- **THEN** 系统置位 bit 后 SHALL 求值命中该等待者并以 payload 唤醒它

#### Scenario: emit 无匹配等待者
- **WHEN** WaitRegistry 中无任何等待者的表达式被新置位的 bit 满足
- **THEN** 系统 SHALL 仅完成既有 bit 置位与 trigger 求值，不唤醒任何节点

#### Scenario: emit 同时驱动 trigger 与 waiter
- **WHEN** 一次 emit 既满足某 Trigger Entity 的 `wait_for`，又满足某挂起 wait 节点的 `wait_for`
- **THEN** 系统 SHALL 既 fire trigger target，又唤醒挂起 wait 节点
