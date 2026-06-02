## Context

DAG 调度内核（`dag/runner.py::run()`）以每节点一个 `asyncio.Task` + 主循环 `asyncio.wait(FIRST_COMPLETED)` 运行。一个 Task 只要不返回即静默挂起，不占 CPU、不阻塞其它独立路径——这是 wait 原语无需改调度内核即可落地的前提。

现有信令栈：
- `EventGroup`（`trigger.py:55`）：`events: set[str]` 内存镜像 + `event_group_bits` 表双写，`load()` 启动重建。bit 状态跨重启存活。
- `TriggerExecutor.emit()`：`set(bit)` + `_record_emit(payload)` 写 `emit_records`，再遍历 trigger 反向索引 `fire()` 启动新 run。
- `NodeRun.status`：自由 TEXT 列，但 `_valid_status` validator 白名单限定为 `{pending, running, succeeded, failed, skipped, cancelled}`。

缺口：`emit()` 只能「启动」新 run（`fire → run_dag/run_node`），无法「唤醒」当前 run 内挂起的节点；`HandlerContext` 无中途收输入 API；状态机无 `waiting`。

## Goals / Non-Goals

**Goals:**
- 新增 `wait` 节点类型，作为 DAG 拓扑层显式、可观测的停顿点。
- 状态机新增 `waiting`，消除「在算 vs 在等」歧义。
- 复用 emit/bit/表达式三件套作为唯一外界输入通道，零新依赖、零新持久化表。
- 重启后经现有 retry/resume 重放即续行。

**Non-Goals:**
- 不做 Web Console 外部触发源配置（webhook/轮询采集层）——独立提案。
- 不做 agent 交互弹窗后端暴露——`agent-intervention-web` change 处理。
- 不暴露 `function` handler 内部的 `ctx.await_input()` 命令式入口（本期只做声明式 wait 节点；handler 内主动等待留作后续，避免黑箱回潮）。

## Decisions

**D1：新增 `wait` 节点类型，而非给任意节点加 `await_input` 标记或在 handler 内暴露 await API。**
理由：等待必须在 DAG 拓扑一眼可见。标记式（节点属性）和 handler 内 API 都把等待藏回节点内部，恰是要消除的黑箱。`wait` 作为第一类顶点，`waiting` 状态天然归属它。备选（标记式 / handler API）被否：违背「显式可见」初衷。

**D2：解锁通道复用 emit，run 隔离靠命名而非靠机制。**
`event:approve:<run_id>` 点对点、`event:market-open` 全局广播，同一套求值器、同一个 `emit()` 入口。`TriggerExecutor` 新增 `WaitRegistry: dict[expr, list[Future]]`，`emit()` 在 `set(bit)` 后除遍历 trigger 外，额外重评 waiter 表达式，命中则 `future.set_result(payload)`。备选（专用 `ResumeNode` RPC）被否：背离「emit 是唯一外界入口」，webhook 还需先转 RPC。备选（节点订阅事件名、无 run_id）被否：多 run 等同名信号串台。

**D3：wait 节点执行体三态。**
```
1. 求值 wait_for 一次 → bit 已置位?
     是 → 取 emit_records 最近 payload → (consume) → return   [信号先到]
     否 ↓
2. status="waiting"; event_bus.publish("node.waiting", wait_for, run_id)
3. 注册 Future 入 WaitRegistry; payload = await wait_for_future(timeout)  [挂起]
4. 解锁 → status="running" → (consume) → return payload
5. 超时 → status="failed", failure_kind="wait_timeout"
```

**D4：信号粒度与生命周期 = run 隔离 + 一次性。**
默认推荐 `event:approve:<run_id>`：run_id 隔离防串台，consume 清 bit 保持 oneshot 语义。重启重放时该 run 的 bit 若已置位则秒过。consume 行为由节点配置 `consume: bool = true` 控制，全局水位信号场景可设 `false`。

**D5：重启恢复复用 `dag-run-control` retry/resume（方案 c），不建 `wait_gates` 表。**
bit（`event_group_bits`）与 payload（`emit_records`）已在 DB 存活，唯一内存态是挂起 Task。重放到 wait 节点重新求值即续行，逻辑幂等。

**D6：`waiting` 不落 `node_runs` validator 白名单之外。**
`_valid_status` 白名单加 `waiting`；`_valid_failure_kind` 加 `wait_timeout`。status 列本身是自由 TEXT，无 DDL 迁移。

## Risks / Trade-offs

- **consume + 重启竞态**：emit 已 consume 但节点 output 未落库时崩溃 → 重放时 bit 已清 → 误重等。→ 缓解：执行体内 **output 持久化先于 consume**；wait 节点回退查 `emit_records` 审计兜底。实现中固定该顺序。
- **WaitRegistry 全量重评成本**：每次 emit 重评所有 waiter，量级与 trigger 反向索引同级。→ 当前规模可接受，必要时按 wait_for token 建反向索引。
- **挂起 Task 与 stop_event 协作**：soft stop 时挂起的 Future 需能被取消。→ wait_for_future 同时 `await stop_event.wait()`，stop 触发则节点按 cancelled 退出（复用 runner 既有 stop 路径）。
- **超时语义边界**：`timeout_seconds` 到期按 failed 而非 optional skip，复用现有失败传播；optional 边语义不变。

## Migration Plan

无 DB schema 迁移（status/failure_kind 为自由 TEXT 列，仅放宽 Pydantic validator）。新节点类型向后兼容：existing DAG 不含 `wait` 节点则行为不变。回滚：移除 `wait` variant 与 WaitRegistry 求值分支即可，无遗留数据结构。

## Open Questions

- wait 节点是否需要默认 payload schema 校验（`parameters_schema` 复用）？倾向本期不强制，payload 透传。
