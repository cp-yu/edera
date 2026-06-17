<!--
路由决策：基于 explore 阶段产出的 Design Summary 直接生成制品。
Design Summary 已确认架构（Startup Sticky Window）、核心组件、数据流、测试策略与风险。
-->

## Why

部分业务 DAG 需要在系统启动后立即运行一次（如启动时拉取初始数据、自检、刷新缓存）。当前系统只在启动时建立 TriggerExecutor 调度视图，没有"启动后自动跑一次"的内建机制，用户只能用 cron 模拟，但 cron 不能精确表达"系统就绪后立刻跑"的语义。

此外，`DagController.start()` 上预留的 `run_startup` 参数被声明但从未被方法体读取，三个调用点全部传 `False`，是死参数；本变更同时清理它。

## What Changes

- 新增 `startup` token 作为 Trigger `wait_for` 表达式的合法触发源，与 `cron`/`event`/`manual` 并列。
- `DagController.start()` 完成运行时初始化后，启动一个**可配置的 startup 窗口**（`system.toml` 的 `startup_window_seconds`，默认 `10`）：
  - 先 `clear` 残留 `startup` bit（防御上次进程崩溃的 DB 残留）。
  - `emit("startup", source="startup")` —— 走标准 `TriggerExecutor.emit()` 路径触发 reverse_index 中的 startup trigger。
  - 创建异步窗口计时任务，到时 `clear` startup bit。
- `startup` bit 是**广播位**：`EventGroup.consume()` 跳过 `startup` token，确保多个 startup trigger 在窗口内共存，互不消费。
- 窗口期内 reload 后新注册的 Waiter / Trigger 可查到 `startup` bit 并按表达式求值；窗口结束后 `startup` 求值恒为 false。
- shutdown 时 cancel 窗口任务并取消所有运行中的 DAG（含 startup 触发的），标记为 cancelled，**重启不补跑**（下次启动是新一次 startup 窗口）。
- 复活 `DagRun.source = "startup"`，归档变更 `2026-06-03-extension-import-clean-runtime` 对该值的删除决策基于"startup 不应触发 DAG"的错误前提，本变更显式推翻。
- **BREAKING**：删除 `DagController.start()` 和 `Engine.start()` 上未使用的 `run_startup` 参数；同步更新三个调用点。
- **BREAKING**：`dag-control` spec 的 "Startup does not run DAG" 要求被改写为"Startup 仅运行显式声明 `startup` 触发的 DAG"。

## Capabilities

### New Capabilities

（无 —— 复用现有 `trigger-system` 与 `dag-control` 能力面）

### Modified Capabilities

- `dag-control`: 改写 "Startup does not run DAG" —— startup 现在会触发显式声明 `wait_for: 'startup'` 的 Trigger 对应的 DAG 一次；其他 DAG 仍不受启动影响。
- `trigger-system`: 新增 startup 作为合法触发源 token；说明 `startup` 是广播位（不参与 consume）；说明 `startup` 触发的 DagRun.source 为 `startup`。

## Impact

- **代码**：
  - `packages/core/src/edera_core/trigger.py`：`EventGroup.consume()` 跳过 `startup`；`emit()` 对 `startup` token 不执行 consume；`_validate_token()` 放行 `startup`。
  - `packages/core/src/edera_core/dag_controller.py`：`start()` 末尾启动窗口；新增 `_startup_window_loop`；`shutdown()` cancel 窗口任务；删除 `run_startup` 参数；为 startup-triggered run 设置 `source="startup"`。
  - `packages/core/src/edera_core/config/schema.py`：`SystemConfig` 新增 `startup_window_seconds: int = 10`。
  - `packages/core/src/edera_core/config/loader.py` / `system.toml`：读取新字段。
  - `packages/core/src/edera_core/engine.py`、`packages/core/src/edera_core/server.py`：删除 `run_startup` 参数及调用点对齐。
- **配置**：`system.toml` 可选新增 `startup_window_seconds`（缺省 10）。
- **API/接口**：`Engine.start()` / `DagController.start()` 签名变更（移除 `run_startup`），属内部 API。
- **数据**：`event_group_bits` 表会有 `startup` 行（窗口期内），窗口结束自动删除；崩溃残留由下次启动 clear。
- **测试**：新增 startup trigger fire、多 trigger 共存、复合表达式、窗口超时、崩溃残留清理、shutdown cancel 等场景的测试。
- **依赖**：无新增。
