<!-- propose-routing: Design Summary found; input length=18; detail score=5/5 from prior explore context; multi-subsystem=true but already decomposed; decision=proceed with generated artifacts for extension-import-clean-runtime. -->
## Why

当前 runtime core 同时存在硬编码启动、自动补默认 cron、手动 run 直连执行等多条 DAG 运行入口，导致 `default` DAG 获得非规范特殊待遇。现在需要把调度入口收敛到 `TriggerExecutor.emit()`，并把可自动创建的配置实例移动到 extension manifest 声明的可审计导入机制。

## What Changes

- 增加 extension manifest 的 `imports.entities` 声明，用于列出 extension 包内要自动导入的 Entity YAML。
- 增加 `extension_imports` 导入索引，记录每条 manifest import path 的导入状态、digest 和实体引用，支撑幂等导入与后续卸载依据。
- 增加独立 extension entity importer：扫描 manifest import 声明后导入一次；已有导入记录跳过；已有 DB Entity 记录 `skipped_existing` 且不覆盖。
- **BREAKING** 删除 `DagController.start()` 启动时自动运行 DAG 的行为。
- **BREAKING** 删除 core runtime/materialization 自动生成 `<dag>-default-cron` trigger 的行为。
- **BREAKING** 删除 `DagRun.source = startup` 合法值。
- 修改手动 DAG run，使 `DagService.Run` 通过 `emit("manual:dag:<name>")` 进入统一调度路径。
- 删除 Web BFF 中 hard-coded `default` DAG 专用兼容路由，调用方使用规范的 `/api/dags/{dag_name}/...` 路径。

## Capabilities

### New Capabilities
- `extension-entity-imports`: extension manifest 声明的 Entity 实例自动导入、导入索引、幂等和卸载依据。

### Modified Capabilities
- `extension-manifest-system`: manifest 支持 `imports.entities`，并保持 scan 只解析声明、不写 DB。
- `db-backed-core-entities`: core runtime 不再生成 node/dag/trigger/resource 实例，运行配置只来自 DB 中已有实体。
- `dag-control`: DAG 启动不再自动运行，手动运行通过 emit 路径进入调度。
- `data-models`: `DagRun.source` 删除 `startup`，仅保留 `manual`、`retry`、`trigger:<id>`。
- `edera-web-bff`: Web BFF 不再提供 hard-coded `default` DAG 专用运行/停止/历史路径。

## Impact

- Affected code: `packages/core/src/edera_core/manifest.py`, `bootstrap.py`, `config/loader.py`, `dag_controller.py`, `trigger.py`, `server.py`, `storage/entities.py`, `storage/repository.py`, `web/routes.py`, proto/client tests if route/API behavior requires adjustment.
- Affected data model: new `extension_imports` table; `DagRun.source` validator changes.
- Affected specs: extension manifest, DB-backed core entities, DAG control, data models, Web BFF.
- Follow-up dependency: `move-workflows-to-extensions` will move current repository DAG content into extension packages using this import mechanism.
