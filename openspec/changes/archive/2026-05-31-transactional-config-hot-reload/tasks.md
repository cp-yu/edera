### Task 1: Runtime snapshot commit

**Goal**: 在 `DagController` 内建立唯一 committed runtime snapshot，并提供事务提交路径。

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/bootstrap.py`
- Test: `tests/core/unit/test_hot_reload.py`

**Requirements**:
- 定义 controller-owned runtime snapshot，包含 `AppConfig`、`BootstrapResult`、`EntityStore`、`TriggerExecutor`、`CronEmitter` 和 extension table names。
- `DagController.start()` SHALL 初始化第一个 committed runtime snapshot。
- `install_snapshot()` SHALL 在候选配置、extension table 创建和 trigger 加载全部成功后才替换 snapshot。
- commit 失败 MUST 保留旧 snapshot。
- 并发 commit SHALL 通过 controller 内部 lock 串行化。

#### Checks

- [x] C1 Verify snapshot commit success
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "Manifest 热加载" / Scenario "Manifest 新增 handler 声明"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k snapshot_commit_success`
  - Expect: candidate snapshot 成功后 handler registry、entity type registry、TriggerExecutor 和 CronEmitter 一起替换

- [x] C2 Verify failed commit preserves old snapshot
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "Manifest 热加载" / Scenario "Manifest candidate 失败保留旧 registries"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k snapshot_commit_failure`
  - Expect: extension 扫描、table 创建或 trigger 加载失败时旧 snapshot 完整保留

- [x] C3 Verify concurrent commits are serialized
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "Snapshot commit serialization" / Scenario "Concurrent reload commits are serialized"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k snapshot_commit_serialized`
  - Expect: 并发 reload commit 不暴露半提交状态

### Task 2: HotReloader and server commit wiring

**Goal**: 让 `HotReloader` 通过 server/controller commit callback 提交候选 snapshot，并只在 commit 成功后 emit。

**Files**:
- Modify: `packages/core/src/edera_core/hot_reload.py`
- Modify: `packages/core/src/edera_core/server.py`
- Test: `tests/core/unit/test_hot_reload.py`
- Test: `tests/core/unit/test_server_hot_reload.py`

**Requirements**:
- `HotReloader.reload_once()` SHALL 构建 candidate `AppConfig` 和 `BootstrapResult` 后调用 commit callback。
- `Server._reload_config()` SHALL 委托 controller 提交 candidate snapshot。
- `event:config-changed` MUST 只在 commit callback 成功后 emit。
- callback 失败 MUST 不 emit 且 watcher 继续运行。
- `emit("event:config-changed")` MUST 使用已提交 snapshot 中的 `TriggerExecutor`。

#### Checks

- [x] C4 Verify successful reload emits after commit
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "配置变更 emit 事件" / Scenario "配置变更 emit 事件"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k emit_config_changed`
  - Expect: reload commit 成功后才 emit `event:config-changed`

- [x] C5 Verify callback failure does not emit
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "热加载失败隔离" / Scenario "reload 失败不 emit"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k failure_isolation`
  - Expect: callback 失败不 emit，watcher 可处理下一次成功 reload

- [x] C6 Verify server reload callback installs snapshot
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "配置文件热加载" / Scenario "Node 配置变更热加载"
  - Command: `uv run pytest tests/core/unit/test_server_hot_reload.py -k reload_installs_snapshot`
  - Expect: `Server._reload_config()` 调用 controller snapshot commit 路径

- [x] C7 Verify config-changed does not reload trigger files
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "配置变更 emit 事件" / Scenario "config-changed 事件不绕过 snapshot"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k config_changed_uses_snapshot`
  - Expect: `emit("event:config-changed")` 不再从文件重新构建 trigger registry

### Task 3: DAG run snapshot isolation

**Goal**: 新 DAG run 捕获当前 committed snapshot，运行中 DAG 不受后续 reload 影响。

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `tests/core/unit/test_hot_reload.py`
- Test: `tests/core/integration/test_dag_runner.py`

**Requirements**:
- `_run()` SHALL 在启动时捕获当前 committed runtime snapshot。
- `_run_single_node()` SHALL 在启动时捕获当前 committed runtime snapshot。
- run 生命周期内 SHALL 使用捕获的 config、registries 和 extension table names。
- 新 run SHALL 使用 reload commit 后的最新 snapshot。
- active run MUST 继续使用启动时捕获的 executor 和 module cache。

#### Checks

- [x] C8 Verify active DAG keeps startup snapshot
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "热加载不影响运行中 DAG" / Scenario "运行中 DAG 不受热加载影响"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k active_run_snapshot_isolation`
  - Expect: run 启动后发生 successful reload，active run 仍使用旧 snapshot

- [x] C9 Verify new DAG run uses committed snapshot
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "热加载不影响运行中 DAG" / Scenario "新 run 使用更新后配置"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k new_run_uses_committed_snapshot`
  - Expect: reload commit 后的新 run 使用新 NodeConfig 和 handler registry

- [x] C10 Verify handler script reload only affects new executors
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "Handler 脚本热加载" / Scenario "Handler 脚本修改后重新加载", Scenario "运行中 handler 不被替换"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k handler_reload_new_executor_only`
  - Expect: 新 executor 重新 import handler，active executor cache 不被清空

### Task 4: Runtime read API snapshot boundary

**Goal**: 让运行时读 API 使用 committed snapshot，同时保留 config edit API 的文件语义。

**Files**:
- Modify: `packages/core/src/edera_core/graph_service.py`
- Modify: `packages/core/src/edera_core/query_service.py`
- Modify: `packages/core/src/edera_core/server.py`
- Modify: `packages/core/src/edera_core/service_common.py`
- Test: `tests/core/unit/test_server_hot_reload.py`

**Requirements**:
- `GraphService` runtime read paths SHALL read committed snapshot for DAG/Node runtime views。
- `EntityService.Get/List/Query` SHALL read committed snapshot for entity runtime views。
- `QueryService` runtime validation/display reads SHALL use committed snapshot where they inspect runtime DAG/entity state。
- `ConfigService` raw config read/write and file editing paths SHALL remain file-backed。
- 保存文件成功 MUST NOT imply runtime snapshot commit success。

#### Checks

- [x] C11 Verify runtime read API sees committed snapshot
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "Runtime read APIs use committed snapshot" / Scenario "Runtime read API sees committed snapshot"
  - Command: `uv run pytest tests/core/unit/test_server_hot_reload.py -k runtime_read_api_committed_snapshot`
  - Expect: reload commit 成功后 Graph/Entity runtime reads 返回新 snapshot

- [x] C12 Verify runtime read API ignores failed candidate
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "Runtime read APIs use committed snapshot" / Scenario "Runtime read API ignores failed candidate"
  - Command: `uv run pytest tests/core/unit/test_server_hot_reload.py -k runtime_read_api_ignores_failed_candidate`
  - Expect: 文件保存但 reload commit 失败后 runtime reads 仍返回旧 snapshot

- [x] C13 Verify config edit API remains file-backed
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "Runtime read APIs use committed snapshot" / Scenario "Config edit API reads file state"
  - Command: `uv run pytest tests/core/unit/test_server_hot_reload.py -k config_edit_api_file_backed`
  - Expect: raw config read 能看到文件内容，但 runtime snapshot 未被失败 candidate 替换

### Task 5: Regression validation

**Goal**: 保持既有 lifecycle、failure isolation 和 trigger/cron 行为不回退。

**Files**:
- Test: `tests/core/unit/test_hot_reload.py`
- Test: `tests/core/unit/test_trigger_system.py`
- Test: `tests/core/unit/test_cron_emitter.py`

**Requirements**:
- reload failure SHALL 继续隔离且不终止 watcher。
- trigger entity 变更 commit 成功后 SHALL 更新 CronEmitter。
- 失败 reload MUST 不触发 cron 重扫描。

#### Checks

- [x] C14 Verify watcher failure isolation remains
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "热加载失败隔离" / Scenario "callback 失败不终止 watcher"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k failure_isolation`
  - Expect: 单次 reload callback 失败后 watcher 继续处理后续变更

- [x] C15 Verify cron registry update and preservation
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "配置变更 emit 事件" / Scenario "trigger entity 变更触发 cron 重扫描", Scenario "失败 reload 不触发 cron 重扫描"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py tests/core/unit/test_cron_emitter.py -k cron`
  - Expect: 成功 commit 更新 CronEmitter，失败 commit 保留旧 CronEmitter
