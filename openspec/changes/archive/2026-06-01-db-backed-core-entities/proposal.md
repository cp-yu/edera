## Why

<!-- propose-routing: Design Summary found; input length=18; detail score=5/5 from prior explore; multi-subsystem=true; decision=proceed using explore Design Summary -->

核心配置型 Entity 仍以 YAML/config 文件作为运行时来源，导致检索、迁移、CLI 操作和 Web Console 审查都绕不开文件语义。当前系统已经有 SQLite、runtime tables、输出型 Entity 数据库层和 gRPC CLI 契约，现在需要把引擎依赖的核心配置型 Entity 收敛到 DB source of truth，避免 YAML 与 DB 双真相。

## What Changes

- **BREAKING**: `node`、`dag`、`trigger`、`resource` 的运行时 source of truth 从 YAML/config 文件迁移到 SQLite。
- 新增固定 per-type tables：`entity_node`、`entity_dag`、`entity_trigger`、`entity_resource`，第一阶段按当前核心模型直接完全列化。
- 新增 DB-backed `entity_types` 元数据，用于记录核心类型 schema、版本、表映射和保护属性。
- `EntityService` / `EntityStore` / runtime snapshot 构建改为从 DB 读取核心配置型 Entity。
- YAML 降级为 CLI import/export/template 文件格式，支持完整 Entity 文档的 `--file` 工作流。
- 明确 runtime 边界：运行中状态以内存 snapshot 为准，`dag_runs`、`node_runs`、`edge_inputs`、`source_recoveries`、`emit_records` 只记录提交事实和查询投影。
- raw stdout/stderr 等大体积日志继续文件落盘，DB 仅保存 `log_index`。

## Capabilities

### New Capabilities
- `db-backed-core-entities`: 核心配置型 Entity 的 DB source-of-truth、固定 per-type tables、YAML import/export/template、runtime snapshot 和 log index 边界。

### Modified Capabilities
- `entity-storage-tiers`: 配置型 Entity 不再以 filesystem 作为运行时 source of truth，核心配置型 Entity 迁移到 DB-backed per-type tables。
- `edera-cli`: `edera entity` 增加 YAML `import`、`export`、`template` 文件工作流。
- `runtime-input-context`: 澄清运行中状态以内存为准，runtime tables 只持久化提交事实并投影为 runtime entities。

## Impact

- 影响 `packages/core/src/edera_core/storage/entities.py`、`storage/repository.py`、`storage/database.py`、Alembic migrations。
- 影响 `packages/core/src/edera_core/config/entities.py`、`config/loader.py`、`bootstrap.py`、`hot_reload.py`、`engine.py`、`dag_controller.py`。
- 影响 `packages/core/src/edera_core/server.py`、`grpc_client.py`、`cli.py`、`proto/edera.proto`。
- 影响 Web Console 通过 BFF/gRPC 获取和审查 Entity 的路径。
- 需要迁移现有 `config/nodes/*.yaml`、`config/dags/*.yaml`、`config/triggers/*.yaml` 和 `resource` 实例。
- 不引入新数据库；继续使用 SQLite + WAL、SQLModel/SQLAlchemy、aiosqlite、Alembic。
