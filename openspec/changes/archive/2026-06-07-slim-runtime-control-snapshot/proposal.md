## Why

当前 `RuntimeSnapshot` 同时承担控制面提交边界、全量 DAG/Node 配置容器和运行时读模型，已经与 DB-backed config、`DagExecutionSnapshot` 和按需 DAG 执行闭包的方向冲突。现在仍处于开发阶段，应直接收敛职责，移除全量启动加载和原地 mutate snapshot 的旧接口。

## What Changes

- 将 `RuntimeSnapshot` 重命名并收敛为 `RuntimeControlSnapshot`，仅保留常驻控制面状态：`system/runtime settings`、`TriggerExecutor`、`CronEmitter` 和可选 generation/version id。
- 在 `DagController` 统一构建 `DAG execution closure`，并在 run start 时冻结到 `DagExecutionSnapshot`。
- `DAG execution closure` 定义为 root DAG、reachable sub-DAGs 和 referenced node types 的最小配置闭包。
- `DagExecutionSnapshot` 冻结执行所需的 `entity_types`、`handler_resolver`、`extension_table_names` 和 run-needed skills。
- Graph/Config/Query 运行时读写改为 DB-backed repository，不再依赖 `runtime_snapshot().config.dags` 或 `runtime_snapshot().config.nodes`。
- **BREAKING** 删除 `ReloadEntityTypes` / `ReloadSkills` RPC、client wrapper、CLI/Web 调用路径。
- **BREAKING** Node trigger target 格式改为 `node:<dag_name>/<node_id>`，不再全局扫描所有 DAG 反查 node id。
- DAG/Node/EntityType/Skill 变更仍 emit `event:config-changed`，但不 rebuild `RuntimeControlSnapshot`。
- `GraphService.SaveDag` 只校验 candidate 可达的 sub-DAG closure，不再全量校验系统所有 DAG。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-hot-reload`: committed runtime snapshot 语义改为 `RuntimeControlSnapshot`，只覆盖控制面 rebuild 和 config-changed emit 边界。
- `dag-execution-snapshot`: 增加 `DAG execution closure` 作为 per-run DAG/Node 最小闭包，并冻结执行所需 metadata。
- `dag-control`: DAG run、retry、resume 和 node trigger 统一通过 `DagController` 构建 execution snapshot；node trigger target 改为 `node:<dag_name>/<node_id>`。
- `grpc-graph-service`: DAG/Node/Skill 图服务读写改为 DB-backed；`SaveDag` 只校验 reachable sub-DAG closure。
- `grpc-config-service`: 删除 `ReloadEntityTypes` / `ReloadSkills`，EntityType/Skill 以 DB 为 source of truth。
- `grpc-query-service`: 查询服务不再依赖 `runtime_snapshot().config.dags/nodes` 做 runtime read validation。
- `database-handler-resolver`: handler resolver 与 extension table mapping 在 `DagExecutionSnapshot` 中按 run 冻结。
- `db-backed-core-entities`: 明确 DAG/Node/EntityType/Skill 运行时读模型从 DB 查询，不进入控制面 snapshot。
- `runtime-entity-type-reload`: 删除运行时 entity type reload API，EntityType 变更通过 DB source of truth 和下一次 `DagExecutionSnapshot` 生效。
- `trigger-system`: Trigger node target 格式改为 `node:<dag_name>/<node_id>`。
- `manual-trigger-prefix`: Manual node emit 格式改为 `manual:node:<dag_name>/<node_id>`，并走 DAG-scoped node execution。
- `trigger-workbench-inspector`: Workbench node trigger 列表和创建使用 DAG-scoped node target。

## Impact

- Affected backend files include `packages/core/src/edera_core/dag_controller.py`, `snapshot.py`, `dag/loader.py`, `dag/runner.py`, `node/executor.py`, `graph_service.py`, `config_service.py`, `query_service.py`, `server.py`, `hot_reload.py`, `storage/repository.py`, `resolver.py`, `grpc_client.py`, and `proto/edera.proto`.
- Existing tests that construct `RuntimeSnapshot` or assert `runtime_snapshot().config.*` must be rewritten around `RuntimeControlSnapshot`, DB-backed reads, and `DagExecutionSnapshot`.
- Existing trigger fixtures using `node:<node_id>` must migrate to `node:<dag_name>/<node_id>`.
- Web Workbench trigger inspector target filtering/creation must include the current DAG name for node triggers.
- No compatibility shim is required for deleted reload RPCs because the project is still in development.
