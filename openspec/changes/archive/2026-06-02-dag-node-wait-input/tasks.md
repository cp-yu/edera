### Task 1: 新增 WaitNodeConfig 节点类型

**Goal**: 在 NodeConfig discriminated union 中新增 `wait` variant，使 `type: "wait"` 配置可被反序列化与校验。

**Files**:
- Modify: `packages/core/src/edera_core/config/schema.py`
- Test: `packages/core/tests/test_wait_node_config.py`

**Requirements**:
- 新增 `WaitNodeConfig(NodeConfigBase)`，字段 `type: Literal["wait"]`、`wait_for: str`、`timeout_seconds: float | None`（继承基类，> 0）、`consume: bool = True`
- `wait_for` 为空时校验失败
- 在 `NodeConfig._variants` 注册 `"wait": WaitNodeConfig`
- function/agent/dag 三变体行为不变

#### Checks

- [x] C1 Verify wait variant 反序列化
  - Verifies: `specs/node-type-discriminated-union/spec.md` / Requirement "NodeConfig 增加 wait variant" / Scenario "反序列化 wait variant"
  - Command: `cd packages/core && pytest tests/test_wait_node_config.py -k variant`
  - Expect: `NodeConfig.model_validate({"type":"wait",...})` 返回 `WaitNodeConfig`

- [x] C2 Verify wait_for 不可为空
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "Wait 节点类型" / Scenario "wait_for 不可为空"
  - Command: `cd packages/core && pytest tests/test_wait_node_config.py -k blank`
  - Expect: 空 `wait_for` 触发 ValidationError

- [x] C3 Verify 现有变体不受影响
  - Verifies: `specs/node-type-discriminated-union/spec.md` / Requirement "NodeConfig 增加 wait variant" / Scenario "现有变体不受影响"
  - Command: `cd packages/core && pytest tests/test_wait_node_config.py -k existing`
  - Expect: function/agent/dag 配置仍解析为各自类型

### Task 2: 扩展 NodeRun 状态机

**Goal**: 在 `NodeRun` validator 中放行 `waiting` 状态与 `wait_timeout` failure_kind。

**Files**:
- Modify: `packages/core/src/edera_core/storage/entities.py`
- Test: `packages/core/tests/test_wait_node_status.py`

**Requirements**:
- `_valid_status` 白名单加入 `waiting`
- `_valid_failure_kind` 白名单加入 `wait_timeout`
- 无 DB schema 迁移（status/failure_kind 为自由 TEXT 列）

#### Checks

- [x] C4 Verify waiting 状态可持久化
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "Waiting 运行状态" / Scenario "挂起期间状态为 waiting"
  - Command: `cd packages/core && pytest tests/test_wait_node_status.py -k waiting`
  - Expect: 构造 `NodeRun(status="waiting")` 不报校验错误

- [x] C5 Verify wait_timeout failure_kind 可持久化
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "超时按失败处理" / Scenario "等待超时"
  - Command: `cd packages/core && pytest tests/test_wait_node_status.py -k timeout`
  - Expect: `NodeRun(failure_kind="wait_timeout")` 不报校验错误

### Task 3: WaitRegistry 与 emit 唤醒通道

**Goal**: 在 `TriggerExecutor` 引入 WaitRegistry，`emit()` 置位 bit 后重评挂起等待者并以 payload 唤醒。

**Files**:
- Modify: `packages/core/src/edera_core/trigger.py`
- Test: `packages/core/tests/test_wait_registry.py`

**Requirements**:
- `TriggerExecutor` 持有 `WaitRegistry`，提供 register（返回 Future）与 unregister
- `emit()` 在 `set(bit)` + `_record_emit` 后重评所有 waiter 的 `wait_for` 表达式（复用现有求值器）
- 命中等待者以最近 emit payload `set_result` 唤醒
- 唤醒后按等待者 `consume` 约定 consume bit
- 不影响既有 trigger fire 路径

#### Checks

- [x] C6 Verify emit 唤醒挂起等待者
  - Verifies: `specs/event-emit-rpc/spec.md` / Requirement "emit 驱动 WaitRegistry 求值" / Scenario "emit 唤醒挂起等待者"
  - Command: `cd packages/core && pytest tests/test_wait_registry.py -k wake`
  - Expect: 注册等待 `event:approve:abc` 后 emit，Future 以 payload resolve

- [x] C7 Verify emit 无匹配不唤醒
  - Verifies: `specs/event-emit-rpc/spec.md` / Requirement "emit 驱动 WaitRegistry 求值" / Scenario "emit 无匹配等待者"
  - Command: `cd packages/core && pytest tests/test_wait_registry.py -k nomatch`
  - Expect: 不匹配 emit 不 resolve 任何 Future

- [x] C8 Verify emit 同时驱动 trigger 与 waiter
  - Verifies: `specs/event-emit-rpc/spec.md` / Requirement "emit 驱动 WaitRegistry 求值" / Scenario "emit 同时驱动 trigger 与 waiter"
  - Command: `cd packages/core && pytest tests/test_wait_registry.py -k both`
  - Expect: 一次 emit 既 fire trigger 又唤醒 waiter

### Task 4: wait 节点执行体三态

**Goal**: 在 executor 新增 `_execute_wait()`，实现信号先到/后到/超时三态，并发布 `node.waiting`。

**Files**:
- Modify: `packages/core/src/edera_core/node/executor.py`
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Test: `packages/core/tests/test_wait_node_execute.py`

**Requirements**:
- `execute()` 新增 `isinstance(config, WaitNodeConfig)` → `_execute_wait()` 分支
- 先求值一次 `wait_for`：bit 已置位则取 emit_records payload 直接返回（不经 waiting）
- 未置位则记 `waiting`、`event_bus.publish("node.waiting", run_id, node, wait_for)`、注册 Future 挂起
- output 持久化先于 consume（防重启竞态）
- `timeout_seconds` 到期标记 `failed` + `failure_kind="wait_timeout"`

#### Checks

- [x] C9 Verify 信号先到直接通过
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "信号先到即直接通过" / Scenario "信号先到"
  - Command: `cd packages/core && pytest tests/test_wait_node_execute.py -k signal_first`
  - Expect: bit 预置位时节点不经 waiting，output 为 emit payload

- [x] C10 Verify 信号后到唤醒
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "信号后到唤醒挂起节点" / Scenario "信号后到唤醒"
  - Command: `cd packages/core && pytest tests/test_wait_node_execute.py -k signal_after`
  - Expect: 先挂起后 emit，output payload 为 emit payload

- [x] C11 Verify 不匹配信号不唤醒
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "信号后到唤醒挂起节点" / Scenario "不匹配信号不唤醒"
  - Command: `cd packages/core && pytest tests/test_wait_node_execute.py -k mismatch`
  - Expect: 不匹配 emit 后节点仍 waiting

- [x] C12 Verify 超时按失败
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "超时按失败处理" / Scenario "等待超时"
  - Command: `cd packages/core && pytest tests/test_wait_node_execute.py -k timeout`
  - Expect: 超时后 status=failed, failure_kind=wait_timeout

- [x] C13 Verify waiting 经 SSE 推送
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "Waiting 状态实时可观测" / Scenario "waiting 经 SSE 推送"
  - Command: `cd packages/core && pytest tests/test_wait_node_execute.py -k publish`
  - Expect: 进入 waiting 时 event_bus 收到 node.waiting 含 run_id/node/wait_for

### Task 5: consume 生命周期与 run 隔离

**Goal**: 验证 consume 开关控制 bit 生命周期，run 隔离信号命名不串台。

**Files**:
- Test: `packages/core/tests/test_wait_node_isolation.py`

**Requirements**:
- `consume: true` 唤醒后清 bit；`consume: false` 保留 bit
- run 隔离信号 `event:approve:<run_id>` 仅唤醒对应 run
- 不引入独立投递机制，纯靠命名

#### Checks

- [x] C14 Verify 一次性与水位信号
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "consume 控制信号生命周期" / Scenario "一次性信号"
  - Command: `cd packages/core && pytest tests/test_wait_node_isolation.py -k consume`
  - Expect: consume=true 清 bit，consume=false 留 bit

- [x] C15 Verify run 隔离不串台
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "Run 隔离靠信号命名" / Scenario "run 隔离不串台"
  - Command: `cd packages/core && pytest tests/test_wait_node_isolation.py -k isolation`
  - Expect: emit run A 信号仅唤醒 run A，run B 仍 waiting

### Task 6: dispatcher 挂起不阻塞与 stop 取消

**Goal**: 验证 wait 节点挂起不阻塞独立路径、唤醒后正常汇入调度、stop 时可取消。

**Files**:
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Test: `packages/core/tests/test_wait_node_dispatcher.py`

**Requirements**:
- wait 节点挂起期间独立路径节点正常执行
- 唤醒后 dispatcher 像普通节点完成一样推进下游
- `stop_event` 置位时解除挂起并按 stop 路径终止
- wait_for_future 同时 await stop_event

#### Checks

- [x] C16 Verify 挂起不阻塞独立路径
  - Verifies: `specs/dag-event-driven-executor/spec.md` / Requirement "Dispatcher 支持 wait 节点挂起" / Scenario "wait 节点挂起不阻塞主循环"
  - Command: `cd packages/core && pytest tests/test_wait_node_dispatcher.py -k independent`
  - Expect: gate 挂起时 worker 正常完成并推进

- [x] C17 Verify 唤醒后汇入调度
  - Verifies: `specs/dag-event-driven-executor/spec.md` / Requirement "Dispatcher 支持 wait 节点挂起" / Scenario "wait 节点唤醒后正常汇入调度"
  - Command: `cd packages/core && pytest tests/test_wait_node_dispatcher.py -k resume`
  - Expect: 唤醒后下游就绪条件被评估并启动

- [x] C18 Verify stop 取消挂起节点
  - Verifies: `specs/dag-event-driven-executor/spec.md` / Requirement "Dispatcher 支持 wait 节点挂起" / Scenario "stop 时取消挂起的 wait 节点"
  - Command: `cd packages/core && pytest tests/test_wait_node_dispatcher.py -k stop`
  - Expect: stop_event 置位后 wait 节点解除挂起并终止

### Task 7: 重启重放恢复

**Goal**: 验证经现有 retry/resume 重放到 wait 节点后按 bit 状态续行或重新挂起。

**Files**:
- Test: `packages/core/tests/test_wait_node_replay.py`

**Requirements**:
- 重放时重新求值 `wait_for`
- bit 已置位（持久于 event_group_bits）则直接通过
- bit 未置位则重新进入 waiting
- 不新增持久化表

#### Checks

- [x] C19 Verify 重启后 bit 置位续行
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "重启重放恢复等待" / Scenario "重启后 bit 仍置位则续行"
  - Command: `cd packages/core && pytest tests/test_wait_node_replay.py -k resume_pass`
  - Expect: bit 持久存在时重放秒过

- [x] C20 Verify 重启后未置位重新挂起
  - Verifies: `specs/dag-node-wait-input/spec.md` / Requirement "重启重放恢复等待" / Scenario "重启后 bit 未置位则重新挂起"
  - Command: `cd packages/core && pytest tests/test_wait_node_replay.py -k resume_wait`
  - Expect: bit 不存在时重放重新进入 waiting

## Remediation

- [x] [code_fix] C18 stopped single-source wait DAG can fail via all-source-failed guard instead of normal stop termination; fix runner stop/cancel path and add focused single-source wait stop coverage.
