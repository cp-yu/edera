<!--
propose-decision:
  designSummary: found (from /opsx:explore)
  routing: skip-explore (Design Summary present)
  scope: change 1 of 2 (wait primitive); change 2 = agent-intervention-web
-->

## Why

DAG 执行中节点要么在算、要么完成，没有「显式等待外界输入」的能力。`function` 节点 handler 同步执行即返回，无中途接收输入的通道；`agent` 节点的子进程虽可在内部等待 tool 输入，但这发生在 subprocess 黑箱里，DAG 与用户都只看到 `running`，无法区分「在算」和「在等人喂」。人工审批、人工质检、等待外部系统回调这类 human-in-the-loop / event-in-the-loop 场景因此无法在 DAG 拓扑层显式表达。

## What Changes

- 新增 `wait` 节点类型（`NodeConfig` discriminated union 第四个 variant），声明 `wait_for` 布尔表达式作为显式停顿点。
- `node_runs.status` 新增第一类公民 `waiting`，与 `running`/`succeeded`/`failed`/`upstream_failed` 并列，消除「在算 vs 在等」的状态歧义。
- 新增 `WaitRegistry`（runtime 内存表 `wait_for → asyncio.Future`），与 trigger 反向索引并列；`TriggerExecutor.emit()` 置位 bit 后额外重新求值 waiter，命中则 resolve future 并按约定 consume。
- wait 节点执行体支持「信号先到即直接通过 / 信号后到则挂起等待 / 超时按失败」三态，复用现有 emit / `event_group_bits` / `emit_records` / 触发器表达式语言，**不新建信令系统、不新建持久化表**。
- 重启恢复复用现有 `dag-run-control` retry/resume：bit 与 payload 已在 DB 存活，重放到 wait 节点重新求值即续行（幂等）。
- wait 节点通过现有 `event_bus` 发布 `node.waiting`，复用 agent-realtime-observability SSE 通道推送给 Web Console。

## Capabilities

### New Capabilities
- `dag-node-wait-input`: wait 节点类型、`waiting` 运行状态、WaitRegistry 与 emit 解锁通道、信号先到/后到/超时三态语义、run 隔离信号命名约定与重启重放恢复。

### Modified Capabilities
- `dag-event-driven-executor`: dispatcher 识别 wait 节点的挂起 Task 不阻塞独立路径（语义澄清，机制已具备）。
- `node-type-discriminated-union`: `NodeConfig` union 增加 `wait` variant。
- `event-emit-rpc`: emit 路径在置位 bit 后额外驱动 WaitRegistry 求值，作为 run 内挂起节点的唤醒入口。

## Impact

- `packages/core/src/edera_core/config/schema.py`：新增 `WaitNodeConfig` 及 union 注册。
- `packages/core/src/edera_core/node/executor.py`：新增 `_execute_wait()` 分支。
- `packages/core/src/edera_core/trigger.py`：`TriggerExecutor` 持有 WaitRegistry，`emit()` 求值唤醒。
- `packages/core/src/edera_core/dag/runner.py`：`_record` 支持 `waiting` 状态写入。
- `packages/core/src/edera_core/storage/entities.py`：`NodeRun.status` 取值集扩展（无 schema 迁移，status 为自由文本列）。
- `packages/core/src/edera_core/events.py`：复用 `event_bus` 发布 `node.waiting`。
- 测试：wait 三态、run 隔离不串台、挂起不阻塞独立路径、重启重放续行。
