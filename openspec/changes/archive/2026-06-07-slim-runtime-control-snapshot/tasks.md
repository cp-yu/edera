### Task 1: RuntimeControlSnapshot boundary

**Goal**: Rename and slim the committed control-plane snapshot.

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/server.py`
- Modify: `packages/core/src/edera_core/hot_reload.py`
- Test: `packages/core/tests/test_dag_controller.py`
- Test: `packages/core/tests/test_hot_reload.py`

**Requirements**:
- Rename `RuntimeSnapshot` to `RuntimeControlSnapshot`.
- Keep only `system/runtime settings`, `TriggerExecutor`, `CronEmitter`, and optional generation/version id in the control snapshot.
- Remove `config.dags`, `config.nodes`, `config.entities`, `config.entity_relations`, `bootstrap`, and `extension_table_names` from the control snapshot.
- Rebuild control snapshot only for system/runtime, trigger, and extension control-plane changes.
- Preserve serialized commit and failure isolation.

#### Checks

- [x] C1 Verify control snapshot does not carry DAG/Node maps
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "Runtime read APIs use DB-backed source" / Scenario "Runtime read API sees DB-backed state"
  - Command: `uv run pytest packages/core/tests/test_dag_controller.py packages/core/tests/test_hot_reload.py`
  - Expect: tests prove controller startup and hot reload do not require `runtime_snapshot().config.dags` or `runtime_snapshot().config.nodes`

- [x] C2 Verify control-plane commit failure preserves old snapshot
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "Snapshot commit serialization" / Scenario "Concurrent control-plane commits are serialized"
  - Command: `uv run pytest packages/core/tests/test_hot_reload.py`
  - Expect: failure and serialization tests pass with `RuntimeControlSnapshot`

### Task 2: DAG execution closure and DagExecutionSnapshot

**Goal**: Build per-run DAG execution snapshots from DB-backed closure data.

**Files**:
- Modify: `packages/core/src/edera_core/snapshot.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/dag/loader.py`
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `packages/core/tests/test_snapshot.py`
- Test: `packages/core/tests/test_dag_controller.py`

**Requirements**:
- Add `DAG execution closure` with root DAG, reachable sub-DAGs, and referenced node types.
- Freeze `entity_types`, handler resolver, extension table mapping, and run-needed skills in `DagExecutionSnapshot`.
- Ensure `DagRunner` and `NodeExecutor` do not query DB for execution config.
- Reject missing node types and sub-DAG cycles before run starts.
- Keep running DAGs isolated from later DB changes.

#### Checks

- [x] C3 Verify closure excludes unrelated DAGs
  - Verifies: `specs/dag-execution-snapshot/spec.md` / Requirement "创建 DAG 执行快照" / Scenario "快照不包含无关 DAG"
  - Command: `uv run pytest packages/core/tests/test_snapshot.py packages/core/tests/test_dag_controller.py`
  - Expect: snapshot tests prove unrelated DAGs are absent from the closure

- [x] C4 Verify reachable sub-DAG closure
  - Verifies: `specs/dag-execution-snapshot/spec.md` / Requirement "DAG execution closure 构建" / Scenario "包含 reachable sub-DAG"
  - Command: `uv run pytest packages/core/tests/test_dag_controller.py`
  - Expect: controller tests prove reachable sub-DAGs and node types are included

- [x] C5 Verify missing node and sub-DAG cycle rejection
  - Verifies: `specs/dag-execution-snapshot/spec.md` / Requirement "DAG execution closure 构建" / Scenario "缺失 node type 阻断启动", "闭包检测 sub-DAG 循环"
  - Command: `uv run pytest packages/core/tests/test_dag_controller.py`
  - Expect: run start fails before creating a DagRun for invalid closure inputs

### Task 3: DB-backed repository reads

**Goal**: Provide bounded indexed reads for DAG/Node/EntityType/Skill runtime consumers.

**Files**:
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Modify: `packages/core/src/edera_core/config/entities.py`
- Test: `packages/core/tests/test_entity_repository.py`
- Test: `packages/core/tests/test_entity_store_preload.py`

**Requirements**:
- Add repository APIs to get DAG by name and Node type by name without listing all core entities.
- Add list APIs for DAG names and Node type summaries for GraphService.
- Keep ordinary entity preload separate from DAG/Node closure loading.
- Preserve DB source of truth for EntityTypes and Skills.

#### Checks

- [x] C6 Verify indexed DAG and Node reads
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "Indexed core entity reads" / Scenario "按名称读取 DAG", "按名称读取 Node type"
  - Command: `uv run pytest packages/core/tests/test_entity_repository.py`
  - Expect: repository tests prove single DAG/Node lookup does not require list-all behavior

- [x] C7 Verify ordinary entity preload remains run-scoped
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "核心配置型 Entity 使用 DB source of truth" / Scenario "运行时从 DB 读取普通 Entity"
  - Command: `uv run pytest packages/core/tests/test_entity_store_preload.py`
  - Expect: existing run-scoped ordinary entity preload behavior remains intact

### Task 4: GraphService DB-backed runtime reads

**Goal**: Remove GraphService dependency on runtime snapshot config maps.

**Files**:
- Modify: `packages/core/src/edera_core/graph_service.py`
- Modify: `packages/core/src/edera_core/service_common.py`
- Test: `packages/core/tests/test_graph_service.py`

**Requirements**:
- `ListDags`, `GetDag`, `CreateDag`, `SaveDag`, and Node-type CRUD read DB directly.
- `SaveDag` validates only candidate reachable sub-DAG closure.
- DAG/Node/Skill writes emit `event:config-changed` and do not rebuild `RuntimeControlSnapshot`.
- Skill CRUD uses DB as source of truth.

#### Checks

- [x] C8 Verify GraphService does not read runtime DAG map
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService DAG CRUD" / Scenario "列出所有 DAG", "获取 DAG 详情"
  - Command: `uv run pytest packages/core/tests/test_graph_service.py`
  - Expect: GraphService tests pass without `runtime_snapshot().config.dags`

- [x] C9 Verify SaveDag reachable-only validation
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService DAG CRUD" / Scenario "保存不相关坏 DAG 不阻断当前 DAG"
  - Command: `uv run pytest packages/core/tests/test_graph_service.py`
  - Expect: saving a valid candidate DAG is not blocked by unrelated invalid DAGs

- [x] C10 Verify graph writes emit without control rebuild
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService Node-type CRUD" / Scenario "更新 node type"
  - Command: `uv run pytest packages/core/tests/test_graph_service.py`
  - Expect: node/DAG/skill writes emit config-changed and leave `RuntimeControlSnapshot` generation unchanged

### Task 5: Config and Query service cleanup

**Goal**: Delete reload RPCs and remove runtime snapshot config read dependencies.

**Files**:
- Modify: `proto/edera.proto`
- Modify: `packages/core/src/edera_core/config_service.py`
- Modify: `packages/core/src/edera_core/query_service.py`
- Modify: `packages/core/src/edera_core/grpc_client.py`
- Test: `packages/core/tests/test_config_service.py`
- Test: `packages/core/tests/test_query_service.py`

**Requirements**:
- Remove `ReloadEntityTypes` and `ReloadSkills` RPCs, handlers, client wrappers, and callers.
- EntityType and Skill saves use DB source of truth and emit `event:config-changed`.
- QueryService source and history validation uses DB-backed repositories or persisted run facts.
- ConfigService must not mutate `RuntimeControlSnapshot` in place.

#### Checks

- [x] C11 Verify reload RPCs are absent
  - Verifies: `specs/grpc-config-service/spec.md` / Requirement "ConfigService reload RPC removal" / Scenario "EntityType reload RPC absent", "Skill reload RPC absent"
  - Command: `uv run pytest packages/core/tests/test_config_service.py`
  - Expect: tests prove reload handlers/client wrappers are removed

- [x] C12 Verify QueryService DB-backed validation
  - Verifies: `specs/grpc-query-service/spec.md` / Requirement "QueryService node output 与 history 查询" / Scenario "DAG 不存在时查询 history"
  - Command: `uv run pytest packages/core/tests/test_query_service.py`
  - Expect: QueryService validates DAG history without `runtime_snapshot().config.dags`

### Task 6: Trigger target and manual node run protocol

**Goal**: Replace global node id lookup with explicit DAG-scoped node targets.

**Files**:
- Modify: `packages/core/src/edera_core/trigger.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/server.py`
- Modify: `packages/core/src/edera_core/cli.py`
- Test: `packages/core/tests/test_dag_controller.py`
- Test: `packages/core/tests/test_grpc_control_services.py`

**Requirements**:
- Parse node trigger targets as `node:<dag_name>/<node_id>`.
- Reject `node:<node_id>` targets.
- Parse manual node emit events as `manual:node:<dag_name>/<node_id>`.
- Reject `manual:node:<node_id>` events.
- Resolve node id or alias only inside the named DAG closure.
- Preserve manual DAG emit path for `manual:dag:<name>`.

#### Checks

- [x] C13 Verify DAG-scoped node trigger
  - Verifies: `specs/trigger-system/spec.md` / Requirement "触发目标" / Scenario "触发 DAG-scoped 单 Node 执行"
  - Command: `uv run pytest packages/core/tests/test_dag_controller.py`
  - Expect: node trigger runs only the node inside the named DAG

- [x] C14 Verify legacy node target is rejected
  - Verifies: `specs/trigger-system/spec.md` / Requirement "触发目标" / Scenario "拒绝全局 Node target"
  - Command: `uv run pytest packages/core/tests/test_dag_controller.py packages/core/tests/test_grpc_control_services.py`
  - Expect: `node:<node_id>` target fails with invalid target error

- [x] C15 Verify manual node uses DAG scope
  - Verifies: `specs/manual-trigger-prefix/spec.md` / Requirement "manual 前缀直接 fire" / Scenario "manual:node 直接 fire DAG-scoped Node", "manual:node legacy target 被拒绝"
  - Command: `uv run pytest packages/core/tests/test_dag_controller.py packages/core/tests/test_grpc_control_services.py`
  - Expect: `manual:node:<dag_name>/<node_id>` fires the DAG-scoped node and `manual:node:<node-id>` is rejected

### Task 7: Web trigger inspector DAG-scoped targets

**Goal**: Update Workbench trigger inspector to generate and filter DAG-scoped node trigger targets.

**Files**:
- Modify: `apps/web-console/src/features/workbench`
- Modify: `apps/web-console/src/features/entities`
- Test: `apps/web-console`

**Requirements**:
- DAG trigger view filters `target = dag:<dag_name>`.
- Node trigger view filters `target = node:<dag_name>/<node_id>`.
- Creating a node trigger writes `target = node:<dag_name>/<node_id>`.
- Switching selected node refreshes the DAG-scoped trigger list.

#### Checks

- [x] C16 Verify node trigger list uses DAG scope
  - Verifies: `specs/trigger-workbench-inspector/spec.md` / Requirement "Inspector Triggers tab" / Scenario "选中 node 显示 DAG-scoped node 级 trigger"
  - Command: `npm run verify`
  - Expect: Workbench trigger inspector lists `node:<dag_name>/<node_id>` triggers for the selected node

- [x] C17 Verify node trigger creation uses DAG scope
  - Verifies: `specs/trigger-workbench-inspector/spec.md` / Requirement "trigger CRUD 操作" / Scenario "创建 node trigger 使用 DAG scope"
  - Command: `npm run verify`
  - Expect: creating a node trigger writes `target = node:<dag_name>/<node_id>`

### Task 8: Handler resolver and extension storage snapshot

**Goal**: Freeze handler metadata and extension table mapping in the same run snapshot.

**Files**:
- Modify: `packages/core/src/edera_core/resolver.py`
- Modify: `packages/core/src/edera_core/bootstrap.py`
- Modify: `packages/core/src/edera_core/snapshot.py`
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `packages/core/tests/test_snapshot.py`
- Test: `packages/core/tests/test_node_executor.py`

**Requirements**:
- `DatabaseHandlerResolver.snapshot(session)` freezes enabled handler metadata.
- Extension table mappings are frozen with the same `DagExecutionSnapshot`.
- Handler `ctx.storage.table()` resolves from the frozen execution snapshot.
- Later extension changes do not affect running snapshots.

#### Checks

- [x] C18 Verify resolver snapshot isolation
  - Verifies: `specs/database-handler-resolver/spec.md` / Requirement "Run-start resolver snapshot" / Scenario "Later extension changes do not affect resolver snapshot"
  - Command: `uv run pytest packages/core/tests/test_snapshot.py packages/core/tests/test_node_executor.py`
  - Expect: running snapshot keeps old handler set after extension metadata changes

- [x] C19 Verify extension table mapping consistency
  - Verifies: `specs/database-handler-resolver/spec.md` / Requirement "Extension table mapping freezes with resolver" / Scenario "Handler storage table mapping is consistent"
  - Command: `uv run pytest packages/core/tests/test_node_executor.py`
  - Expect: handler storage table lookup uses mapping frozen in the same `DagExecutionSnapshot`
