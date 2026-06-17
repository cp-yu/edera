### Task 1: 扩展 TriggerExecutor 与 EventGroup 支持 startup 广播位

**Goal**: 让 `startup` 成为合法 trigger token，且在 `consume()` 路径上跳过 `startup`，使多 trigger 共存。

**Files**:
- Modify: `packages/core/src/edera_core/trigger.py`
- Test: `packages/core/tests/test_trigger_system.py`

**Requirements**:
- `_validate_token` 放行 `startup`（与 `cron:"..."` / `event:<name>` 同级合法 token）
- `EventGroup.consume(tokens)` 在入口处过滤掉 `startup`，确保任何调用点都无法清掉它
- `TriggerExecutor.emit()` 路径中 `consume(matched_tokens - waiters.active_tokens())` 自然继承过滤，无需额外特例

#### Checks

- [x] C1 验证 startup token 通过表达式校验
  - Verifies: `specs/trigger-system/spec.md` / Requirement "Trigger Entity 定义" / Scenario "定义 startup 触发器"
  - Command: `cd packages/core && pytest tests/test_trigger_system.py -k startup_token_validates`
  - Expect: `TriggerExpression('startup')` 构造不抛异常；tokens 集合等于 `{"startup"}`

- [x] C2 验证 startup 不被 consume 移除
  - Verifies: `specs/trigger-system/spec.md` / Requirement "Startup token is a broadcast window bit" / Scenario "Startup token does not consume on fire"
  - Command: `cd packages/core && pytest tests/test_trigger_system.py -k startup_not_consumed_on_fire`
  - Expect: 两个 `wait_for: 'startup'` trigger 在 `emit("startup")` 后都 fire；`EventGroup.events` 仍含 `startup`

### Task 2: DagController 启动窗口与 shutdown 取消

**Goal**: 在 `DagController.start()` 末尾打开 startup 窗口，到时清理；`shutdown()` 取消窗口任务与运行中 startup DAG。

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `packages/core/tests/test_dag_controller.py`

**Requirements**:
- `start()` 末尾流程：`events.clear("startup")` → `emit("startup", source="startup")` → `create_task(self._startup_window_loop(window_seconds))`
- 新增 `_startup_window_loop(seconds)`：`await asyncio.sleep(seconds)` 然后 `events.clear("startup")`
- `shutdown()` 中 cancel `_startup_window_task`，并已有 active_runs cancel 逻辑保持不变
- startup 触发的 DagRun.source 设为 `"startup"`（在 fire 路径或 start_run 路径上转换 source）
- 删除 `run_startup` 参数及方法体内对它的引用

#### Checks

- [x] C3 验证启动时单个 startup trigger 触发一次
  - Verifies: `specs/dag-control/spec.md` / Requirement "Startup window auto-runs declared startup triggers" / Scenario "Startup fires single declared startup trigger"
  - Command: `cd packages/core && pytest tests/test_dag_controller.py -k startup_single_trigger_fires_once`
  - Expect: 一个 `wait_for: 'startup'` trigger → 恰好一个 DagRun，source=`"startup"`；`startup` bit 仍在 EventGroup

- [x] C4 验证多 startup trigger 并发触发不互相消费
  - Verifies: `specs/dag-control/spec.md` / Requirement "Startup window auto-runs declared startup triggers" / Scenario "Startup fires multiple declared startup triggers concurrently"
  - Command: `cd packages/core && pytest tests/test_dag_controller.py -k startup_multiple_triggers_concurrent`
  - Expect: 三个不同 target 的 startup trigger → 三个 DagRun，source 全为 `"startup"`；首个 fire 后 `startup` bit 仍在

- [x] C5 验证窗口到期后 startup bit 被清除
  - Verifies: `specs/dag-control/spec.md` / Requirement "Startup window auto-runs declared startup triggers" / Scenario "Startup window expires and clears bit"
  - Command: `cd packages/core && pytest tests/test_dag_controller.py -k startup_window_expires_clears_bit`
  - Expect: 配置 `startup_window_seconds = 0.1`，await sleep 0.2s 后，`EventGroup.events` 不含 `startup`；新 Trigger 求值 false

- [x] C6 验证窗口长度可配置且默认 10 秒
  - Verifies: `specs/dag-control/spec.md` / Requirement "Startup window auto-runs declared startup triggers" / Scenario "Startup window length is configurable"
  - Command: `cd packages/core && pytest tests/test_dag_controller.py -k startup_window_configurable`
  - Expect: `system.toml` 设置 `startup_window_seconds = 1` → 1s 后 bit clear；缺省 → 10s 后 clear

- [x] C7 验证启动前清理崩溃残留 bit
  - Verifies: `specs/dag-control/spec.md` / Requirement "Startup window auto-runs declared startup triggers" / Scenario "Crashed-process residue is cleared before opening window"
  - Command: `cd packages/core && pytest tests/test_dag_controller.py -k startup_clears_residue_before_window`
  - Expect: 预先在 `event_group_bits` 插入 `startup` 行，`start()` 后该行被新窗口替换；表内仅一行 `startup`

- [x] C8 验证 shutdown 取消窗口期内运行中的 startup DAG 且不补跑
  - Verifies: `specs/dag-control/spec.md` / Requirement "Startup window auto-runs declared startup triggers" / Scenario "Shutdown cancels in-flight startup-triggered runs without replay"
  - Command: `cd packages/core && pytest tests/test_dag_controller.py -k shutdown_cancels_startup_run_no_replay`
  - Expect: 启动触发 DAG → shutdown → DagRun 状态 cancelled；重新 `start()` 不会自动续跑该 run

- [x] C9 验证窗口期内复合表达式触发
  - Verifies: `specs/dag-control/spec.md` / Requirement "Startup window auto-runs declared startup triggers" / Scenario "Startup trigger fires with compound expression within window"
  - Command: `cd packages/core && pytest tests/test_dag_controller.py -k startup_compound_expression_within_window`
  - Expect: `wait_for: 'startup AND event:market-open'`，窗口期内 emit `event:market-open` → fire 一次；DagRun.source=`"startup"`

### Task 3: SystemConfig 新增 startup_window_seconds 配置项

**Goal**: 让窗口长度可配置，缺省 10 秒。

**Files**:
- Modify: `packages/core/src/edera_core/config/schema.py`
- Modify: `packages/core/src/edera_core/config/loader.py`
- Modify: `config/system.toml`
- Test: `packages/core/tests/test_config_loader.py`

**Requirements**:
- `SystemConfig` 增加 `startup_window_seconds: int = 10` 字段
- `load_system_config` 从 `system.toml` 读取该字段，缺省 10
- `system.toml` 模板/示例中加入注释说明

#### Checks

- [x] C10 验证缺省值为 10
  - Verifies: `specs/dag-control/spec.md` / Requirement "Startup window auto-runs declared startup triggers" / Scenario "Startup window length is configurable"
  - Command: `cd packages/core && pytest tests/test_config_loader.py -k startup_window_default_10`
  - Expect: 不设置字段时 `SystemConfig.startup_window_seconds == 10`

- [x] C11 验证可读取自定义值
  - Verifies: `specs/dag-control/spec.md` / Requirement "Startup window auto-runs declared startup triggers" / Scenario "Startup window length is configurable"
  - Command: `cd packages/core && pytest tests/test_config_loader.py -k startup_window_custom_value`
  - Expect: `system.toml` 写入 `startup_window_seconds = 1` → 加载结果为 1

### Task 4: 删除死参数 run_startup 并对齐调用点

**Goal**: 清理 `DagController.start()` / `Engine.start()` 上从未被读取的 `run_startup` 参数；同步三个调用点。

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/engine.py`
- Modify: `packages/core/src/edera_core/server.py`

**Requirements**:
- `DagController.start()` 签名移除 `run_startup: bool = True`
- `Engine.start()` 签名移除 `run_startup: bool = False` 及对 controller 的转发
- `server.py:109`、`dag_controller.py` 内两处自调用去掉 `run_startup=False`

#### Checks

- [x] C12 验证代码库不再出现 run_startup 标识符
  - Verifies: `specs/dag-control/spec.md` / REMOVED Requirement "run_startup parameter"
  - Command: `grep -rn "run_startup" packages/ apps/ extensions/ 2>/dev/null || echo "no matches"`
  - Expect: 无任何匹配

- [x] C13 验证删除参数后 Server 启动路径行为等价
  - Preserves: `openspec/specs/dag-control/spec.md` / Requirement "Startup does not run DAG" / Scenario "Controller start is idle for non-startup DAGs"
  - Command: `cd packages/core && pytest tests/test_dag_controller.py -k controller_start_idle_no_startup_trigger`
  - Expect: 旧形式 `controller.start(run_startup=False)` 不再存在；无 startup trigger 声明时 `start()` 不创建 DagRun、不进入 active_runs

### Task 5: 同步 GLOSSARY 中 startup 作为 source 的说明

**Goal**: 在 `GLOSSARY.md` 中明确 `startup` 是合法 `dag_runs.source` 值，并说明其语义（startup 窗口触发的 run）。

**Files**:
- Modify: `GLOSSARY.md`

**Requirements**:
- `dag_runs.source` 合法值列表包含 `manual`、`startup`、`retry`、`trigger:<trigger_name>`
- 注释说明 `startup` 出现在 startup 窗口期内由 `wait_for: 'startup'` 触发的 run

#### Checks

- [x] C14 验证 GLOSSARY 列出 startup 为合法 source
  - Verifies: `specs/dag-control/spec.md` / Requirement "Startup window auto-runs declared startup triggers" / Scenario "Startup fires single declared startup trigger"
  - Command: `grep -n "startup" GLOSSARY.md | grep -i "source"`
  - Expect: 至少一处匹配，明确将 `startup` 列为 `dag_runs.source` 合法值

## Remediation

- [x] R1 [code_fix] 放行 DagRun.source = "startup"
  - Issue: DagRun._valid_source 拒绝 "startup"，违反 dag-control/trigger-system spec 与 proposal
  - Fix: packages/core/src/edera_core/storage/entities.py 在合法集合中加入 "startup"
  - Covers: Task 2 / spec "Startup window auto-runs declared startup triggers" 与 "Startup token is a broadcast window bit"
  - Evidence: packages/core/tests/test_trigger_system.py::test_dag_run_accepts_startup_source

- [x] R2 [artifact_fix] 补全 opsx-delta.yaml 对 cap.data.data-models 的 MODIFIED
  - Issue: opsx-delta 漏掉 data-models capability，与 spec/proposal/GLOSSARY 不一致
  - Fix: openspec/changes/add-startup-trigger/opsx-delta.yaml 增加 cap.data.data-models 条目，将 source 合法集对齐到 manual/startup/retry/trigger:<name>
  - Covers: 全变更
