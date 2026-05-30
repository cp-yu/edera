### Task 1: Bootstrap fallback and BFF discovery

**Goal**: 让 `edera-server` 在生产端口冲突时退避 bootstrap port，并让同机 `edera-web` 通过本机状态文件发现实际端口。

**Files**:
- Modify: `packages/core/src/edera_core/server.py`
- Modify: `packages/core/src/edera_core/web/__main__.py`
- Modify: `README.md`
- Test: `tests/core/unit/test_bootstrap_fallback.py`
- Test: `tests/core/unit/test_web_bootstrap_discovery.py`

**Requirements**:
- Bootstrap bind 地址固定为 `127.0.0.1`，端口从 `9091` 开始有界退避到首个可用端口。
- 成功启动后写入 `EDERA_DATA_DIR/bootstrap.json`，内容只包含 `host` 与 `port`。
- fallback 范围耗尽时 `edera-server` 启动失败并给出明确错误。
- `edera-web` 非 dev 模式读取 `bootstrap.json`，按实际端口请求 `bff:web-console` cert。
- 远程 client 文档说明按实际 bootstrap port 建立 SSH tunnel。

#### Checks

- [x] C1 Verify bootstrap port fallback
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "Bootstrap 端口硬绑 localhost" / Scenario "Bootstrap 端口退避"
  - Command: `uv run pytest tests/core/unit/test_bootstrap_fallback.py -k fallback`
  - Expect: 占用 `127.0.0.1:9091` 后 server 绑定 fallback 范围内首个可用端口

- [x] C2 Verify bootstrap status file
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "Bootstrap 端口硬绑 localhost" / Scenario "Bootstrap 状态文件"
  - Command: `uv run pytest tests/core/unit/test_bootstrap_fallback.py -k status_file`
  - Expect: `bootstrap.json` 只包含 `host=127.0.0.1` 与实际 `port`，不包含 cert/token/server address

- [x] C3 Verify edera-web bootstrap discovery
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "BFF cert 内存模式" / Scenario "启动时拿 cert"
  - Command: `uv run pytest tests/core/unit/test_web_bootstrap_discovery.py -k discovery`
  - Expect: `edera-web` 使用 `bootstrap.json` 中端口初始化 BFF cert

- [x] C4 Verify missing bootstrap status fails fast
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "BFF cert 内存模式" / Scenario "bootstrap 状态缺失"
  - Command: `uv run pytest tests/core/unit/test_web_bootstrap_discovery.py -k missing_status`
  - Expect: 缺失或非法 `bootstrap.json` 使 `edera-web` 明确失败

### Task 2: Hot reload A+ lifecycle and failure isolation

**Goal**: 将 `HotReloader.watch()` 接入 `edera-server` 生命周期，并保证失败 reload 不 emit、不杀 watcher。

**Files**:
- Modify: `packages/core/src/edera_core/server.py`
- Modify: `packages/core/src/edera_core/hot_reload.py`
- Test: `tests/core/unit/test_hot_reload.py`
- Test: `tests/core/unit/test_server_hot_reload.py`

**Requirements**:
- `edera-server.start()` 启动 hot reload watcher task。
- `edera-server.stop()` 取消 watcher task。
- reload 成功后才通过 controller 路径 emit `event:config-changed`。
- 配置解析、extension 扫描或 callback 失败时不 emit。
- 单次失败 reload 后 watcher 继续监听后续变更。

#### Checks

- [x] C5 Verify server starts and stops watcher
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "HotReloader server 生命周期" / Scenario "server 启动 watcher", Scenario "server 停止 watcher"
  - Command: `uv run pytest tests/core/unit/test_server_hot_reload.py -k lifecycle`
  - Expect: server start 创建 watcher task，server stop 取消 watcher task

- [x] C6 Verify successful reload emits config changed
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "配置变更 emit 事件" / Scenario "配置变更 emit 事件"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k emit_config_changed`
  - Expect: reload 成功后 emit `event:config-changed`

- [x] C7 Verify failed reload is isolated
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "热加载失败隔离" / Scenario "reload 失败不 emit", Scenario "callback 失败不终止 watcher"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py -k failure_isolation`
  - Expect: 失败 reload 不 emit，watcher 仍能处理下一次成功 reload

- [x] C8 Verify failed trigger reload preserves cron registry
  - Verifies: `specs/config-hot-reload/spec.md` / Requirement "配置变更 emit 事件" / Scenario "失败 reload 不触发 cron 重扫描"
  - Command: `uv run pytest tests/core/test_event_control_service.py -k config_changed`
  - Expect: 失败 reload 不改变失败前的 cron emitter 注册表

### Task 3: GraphService optional round-trip

**Goal**: 后端 graph payload 在 GET、SAVE 和 SAVE response 中保留 node instance optional 与 edge optional。

**Files**:
- Modify: `packages/core/src/edera_core/graph_service.py`
- Modify: `packages/core/src/edera_core/service_common.py`
- Test: `packages/core/tests/test_graph_service.py`
- Test: `tests/core/unit/test_config_editor.py`

**Requirements**:
- `GraphService.GetDag` 返回 node instance `optional` 和 edge `optional`。
- `graph_dag_payload()` 保存 `DagNodeInstance.optional` 与 `DagEdge.optional`。
- `GraphService.SaveDag` response 保留保存后的 optional 字段。
- 不改变 `NodeConfig.optional` 的类型级语法糖语义。
- 不破坏 `fan_in`、`fan_out`、`fan_in_mode` 保存行为。

#### Checks

- [x] C9 Verify GraphService optional save response
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService DAG CRUD" / Scenario "保存 DAG"
  - Command: `uv run pytest packages/core/tests/test_graph_service.py -k optional`
  - Expect: SaveDag response 保留 node instance optional 与 edge optional

- [x] C10 Verify optional round-trip
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService DAG CRUD" / Scenario "optional round-trip"
  - Command: `uv run pytest packages/core/tests/test_graph_service.py -k optional_round_trip`
  - Expect: GET 后不修改 optional 再 SAVE，配置文件和响应都不丢字段

- [x] C11 Verify effective edge optional semantics
  - Verifies: `specs/edge-optional/spec.md` / Requirement "节点级 Optional 语法糖" / Scenario "effective edge optional 判定", Scenario "节点 optional 不创建第二套运行语义"
  - Command: `uv run pytest tests/core/unit/test_config_editor.py -k optional`
  - Expect: edge、instance、type 三种声明入口只影响 effective edge optional

### Task 4: Workbench optional controls

**Goal**: 在 workbench Inspector 中提供边级 optional 与当前 DAG 节点实例 optional 配置，并保证前端 graph draft 不丢字段。

**Files**:
- Modify: `apps/web-console/src/api/types.ts`
- Modify: `apps/web-console/src/features/workbench/components/Inspector.tsx`
- Modify: `apps/web-console/src/features/workbench/lib/graph.ts`
- Modify: `apps/web-console/src/features/workbench/components/Canvas.tsx`
- Test: `tests/core/e2e/test_inspector.py`

**Requirements**:
- Edge Inspector 展示并保存 `optional` 开关。
- Node Inspector 展示并保存当前 DAG node instance `optional` 开关。
- Node instance optional 文案表达作用范围为当前 DAG 当前实例。
- 前端 `toDagDraft()`、edge hydration 和 node draft 保留 optional 字段。
- 不从 DAG workbench 修改全局 `NodeConfig.optional`。

#### Checks

- [x] C12 Verify edge optional Inspector control
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Edge configuration in Inspector" / Scenario "Select edge shows config", Scenario "Toggle optional"
  - Command: `uv run pytest tests/core/e2e/test_inspector.py -k optional`
  - Expect: Inspector 源码或测试覆盖 edge optional toggle 与保存 payload

- [x] C13 Verify node instance optional Inspector control
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node instance optional configuration in Inspector" / Scenario "Select node shows instance optional", Scenario "Toggle node instance optional"
  - Command: `uv run pytest tests/core/e2e/test_inspector.py -k optional`
  - Expect: Inspector 覆盖 node instance optional toggle，保存 `DagNodeInstance.optional` 且不写全局 NodeConfig

- [x] C14 Verify frontend build
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node instance optional configuration in Inspector" / Scenario "Toggle node instance optional"
  - Command: `cd apps/web-console && npm run build`
  - Expect: TypeScript build passes with optional fields in API and graph types
