## Context

`DagController.start()` 完成 `load_bootstrap` → `install_snapshot` → `scheduler.start` → `_cron_task` 创建后，系统进入"运行时就绪"。部分 DAG 需要在此刻立即运行一次，但现有体系只有 cron / event / manual 三种触发源，缺少"启动就绪"语义。

现状的两个遗留：

1. **`run_startup` 参数**：`DagController.start(run_startup: bool = True)`、`Engine.start(run_startup=False)`、`server.py:109` `controller.start(run_startup=False)`、`dag_controller.py:989/1017` 两处自调用 —— 参数声明但方法体从不读取，是死参数。
2. **历史决策**：归档变更 `2026-06-03-extension-import-clean-runtime` 删除了 `DagRun.source = startup`，并把"不新增 `event:startup` emit"列为 Non-Goal；该决策基于"startup 不应触发 DAG"的前提，本变更显式推翻这一前提。

## Goals / Non-Goals

**Goals:**

- 支持业务方通过 Trigger `wait_for: 'startup'` 声明"启动后跑一次"的 DAG，与现有 cron/event/manual 触发器机制统一。
- 支持多 DAG 同时声明 startup 触发，互不消费。
- 支持复合表达式（如 `startup AND event:market-open`）。
- 进程崩溃 / 重启场景语义清晰：残留 bit 在下次启动时清理；运行中的 startup DAG 在 shutdown 时被 cancel，不补跑。
- 清理死参数 `run_startup`，让 `start()` 签名诚实表达行为。

**Non-Goals:**

- 不补跑历史窗口期内未触发的 trigger（窗口结束即关闭机会）。
- 不变更 cron / event / manual 触发器语义。
- 不变更 `EventGroup` 持久化机制整体设计，仅在 `consume()` 路径为 `startup` 开特例。
- 不引入 startup 触发的优先级 / 顺序保证（多 DAG 并发触发，执行顺序由 DAG runner 既有调度决定）。

## Decisions

### D1：用时间窗口（Sticky Window）而非一次性 emit

**选择**：`DagController.start()` 末尾 `emit("startup")`，随后启动 N 秒计时器（默认 10s，可配置），到时 `clear`。窗口期内 `startup` bit 持续可见。

**理由**：
- **多 trigger 共存**：reverse_index 扫描时所有 `wait_for` 含 `startup` 的 trigger 同时求值为 true，并发 fire。
- **reload 后注册的 Waiter / Trigger 可见**：窗口期内 hot-reload 重建 trigger_executor 后，新加入的 startup trigger 求值仍为 true；窗口外则不可见。语义符合"启动后 N 秒内仍认为是启动阶段"。
- **复合表达式天然有效**：`startup AND event:X` 在窗口期内若 `X` 也置位，立即触发；窗口外 `startup` 求值 false，整个表达式 false。
- **崩溃残留可清理**：下次启动第一步 `clear` 即可。

**备选**：
- *一次性瞬态 emit（fire-and-forget）*：reload 后新 Waiter 拿不到。否决 —— reload 是常见操作，不应丢失 startup 触发机会。
- *持久化 latch（永久位）*：每次启动都会重复触发历史 DAG。否决 —— 违反"每次启动跑一次"的语义。
- *DAG.run_on_startup 字段（不走 trigger）*：实现简单但失去复合表达式与统一 trigger 体系。否决 —— 与现有 trigger 模型不一致。

### D2：`startup` 是广播位，不参与 consume

**选择**：`EventGroup.consume()` 跳过 `startup` token；`TriggerExecutor.emit()` 内部对 `startup` 也跳过 consume 路径。

**理由**：
- 现有 `consume()` 语义是"fire 后清除已匹配 token，避免重复触发"（trigger.py:224）。若 `startup` 也被 consume，第一个 fire 的 startup trigger 会清掉 bit，后续 trigger 求值 false，违反"多 trigger 共存"目标。
- `startup` 是"系统状态"而非"一次性事件"：在窗口期内它是持续 true 的条件，不应被任何单个消费者私有清除。
- 清除时机唯一：窗口计时器到点统一 `clear`。

**实现**：在 `EventGroup.consume(tokens)` 入口处 `tokens = {t for t in tokens if t != "startup"}`；或在 `emit()` 调用 `consume()` 前 filter。前者更彻底（防御其他调用点）。

### D3：窗口长度可配置，默认 10 秒

**选择**：`system.toml` 新增 `startup_window_seconds`，缺省 10。

**理由**：
- 10 秒覆盖典型场景：reload 完成、bootstrap DAG 启动并走到首个 wait 节点、首个外部 event 触发。
- 不同部署（如冷启动较慢的设备）可调大；测试场景可调小到 0.1 加速。
- 配置项缺省值即"开箱即用"行为，不强求用户配置。

**备选**：硬编码 10。否决 —— 测试与不同硬件部署需要可调。

### D4：`DagRun.source = "startup"`，fire 内部 source = `"trigger:<id>"`

**选择**：
- `TriggerExecutor.fire(target, source="trigger:<id>")` 保持现有约定（trigger.py:222）。
- DagController 在 startup trigger 触发的 fire 路径上，将最终 DagRun.source 转换为 `"startup"`。

**理由**：
- 保留 fire 内部 source 的现有约定（便于 trace 哪个 trigger 触发的）。
- DagRun.source 是面向用户/observability 的语义标签，复活历史值 `startup` 让查询"哪些 run 是启动触发的"成为可能。
- 实现上：在 controller 层判断"本次 fire 来自 startup emit 路径"并改写 source；或在 trigger executor 层传一个 hint。

**实现**：emit 时把 `source="startup"` 透传，在 controller 的 `start_run` 路径上根据该 source 决定 DagRun.source。

### D5：窗口期内 reload 不重复 fire 已 fire 的 trigger

**选择**：依赖现有机制 —— `install_snapshot` 重建 trigger_executor 时**不会自动 emit**；只有显式 `emit("startup")` 才触发 reverse_index。因此 reload 本身不会让已 fire 的 startup trigger 再次 fire。

**理由**：
- HotReloader 触发的 `install_snapshot` 只重建调度视图，不重新跑 emit 路径（dag_controller.py:231-267）。
- 但 reload 后**新加入的** startup trigger 仍可能在窗口期内被外部 emit 触发（若有）；本变更不引入 reload 自动 emit startup 的行为。
- 已 fire 的 startup trigger 若不是 oneshot cron，下次 reload 不会因为 reverse_index 重扫而再次 fire（reverse_index 仅在 emit 调用时被查阅）。

**风险**：若窗口期内有 hot-reload + 后续 `emit("event:X")` 调用，且某 trigger 表达式为 `startup AND event:X`，则该 trigger 会 fire 一次。这是预期行为（窗口期内 startup 持续可见）。

### D6：删除死参数 `run_startup`

**选择**：移除 `DagController.start()` / `Engine.start()` 的 `run_startup`；更新三个调用点。

**理由**：项目处于开发阶段无历史负担，死参数应清理而非复活其语义；新功能不需要开关，startup 触发是 trigger 声明驱动的（没声明 startup trigger 就不会跑）。

**备选**：保留作为开关。否决 —— 隐式默认值会让"启动行为"取决于易被遗忘的 bool。

### D7：崩溃残留由下次启动 clear

**选择**：`DagController.start()` 启动窗口前，先 `events.clear("startup")`。

**理由**：
- 进程崩溃时窗口计时器未触发，DB 中残留 `startup` bit。
- 若不清，下次启动的首次 emit 会因 EventGroup.load() 已加载残留而状态混乱（虽然本变更窗口逻辑会立即重设，但显式 clear 让不变量更清晰）。
- 与 cron-emitter "错过 tick 不补跑" 的清理哲学一致。

## Risks / Trade-offs

- **[窗口长度选错]** 太短 → reload 慢的部署错过触发；太长 → 启动后过久才到的外部事件可能误触发复合表达式。**缓解**：可配置 + 缺省 10s。
- **[窗口期内 reload 后新 trigger 不会自动 fire]** 用户在窗口期内通过 reload 添加新 startup trigger，需等到下一次显式 emit 才触发。**接受**：reload 加 trigger 是低频操作，且窗口期内本来就不应频繁改配置；用户可手动 emit `startup` 或重启。
- **[shutdown 时窗口期内 startup DAG 被 cancel]** 用户期望"启动跑一次"，但若 DAG 跑得慢且 edera 被关闭，DAG 失败。**接受**：与 edera 关闭即失败的现有行为一致；下次启动是新一次 startup 窗口，会重新触发。
- **[复合表达式 `startup AND cron:"..."` 语义模糊]** cron 是时间点匹配，startup 是窗口条件，两者 AND 的含义是"窗口期内 cron 也匹配"。**接受**：语义可解释；用户应理解 startup 在窗口期内恒 true。
- **[`source = "startup"` 复活与归档决策对立]** 归档变更 `2026-06-03` 删除了它。**处置**：本变更 design.md 显式记录推翻理由，spec 同步更新。
- **[`run_startup` 删除是 BREAKING]** 三个内部调用点需更新。**接受**：grep 显示无外部消费者。

## Migration Plan

无数据迁移。变更只涉及代码与 spec 同步：

1. 扩展 trigger.py 支持 `startup` token 与广播位语义。
2. 在 `dag_controller.py` `start()` / `shutdown()` 加窗口逻辑；新增 `_startup_window_loop`。
3. `SystemConfig` 加 `startup_window_seconds`。
4. 删除 `run_startup` 参数及三个调用点对齐。
5. 改写 `dag-control` spec 的 "Startup does not run DAG"。
6. 新增/更新测试。

回滚策略：纯代码回滚。DB 残留的 `startup` bit 会在下次启动时被新代码 clear；若回滚到旧代码，残留 bit 不会造成功能问题（旧代码不识别 `startup` token，emit 会失败但不影响其他事件）。

## Open Questions

无。所有关键决策（建模方式、窗口长度来源、consume 语义、source 命名、reload 行为、shutdown 行为、参数清理、残留清理）已在 explore 阶段与用户确认。
