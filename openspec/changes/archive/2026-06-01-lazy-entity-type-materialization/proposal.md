## Why

<!-- propose-routing: Design Summary found; input length=18; detail score=5/5 from prior explore; multi-subsystem=true; decision=proceed using explore Design Summary -->

核心 Entity 入库后，普通 EntityType 仍需要支持类型增减、字段演进和查询性能优化。直接对每次 schema 变化立即执行动态 DDL 会把 SQLite 迁移、回滚和索引维护压到主流程上，因此需要把普通类型的 per-type table 与 lazy 字段物化作为第二阶段单独设计。

## What Changes

- 普通 EntityType 获得独立 `entity_<type>` 表，但新增或未知字段先写入 `attributes_json`。
- EntityType metadata 增加 materialized fields、deprecated fields、schema_version 和 table mapping。
- 支持将稳定、高频或显式声明 indexed 的字段 lazy materialize 为真实列，并回填历史数据。
- 动态删除字段先停止读写并标记 deprecated，后续维护窗口再清理列。
- 增加维护型 CLI/API，用于检查、执行和验证字段物化任务。
- 明确第二阶段不改变核心 `node`、`dag`、`trigger`、`resource` 的第一阶段固定列化表，不合并输出型 Entity 表。

## Capabilities

### New Capabilities
- `lazy-entity-type-materialization`: 普通 EntityType 的 per-type tables、`attributes_json` 承接、lazy 字段物化、deprecated 字段生命周期和维护命令。

### Modified Capabilities
- `extension-declarative-storage`: 动态表创建能力需要与 EntityType per-type table 和 materialized field 元数据保持命名与 DDL 边界一致。
- `entity-system`: 普通 EntityType 的字段变化语义从静态 schema 校验扩展为 `attributes_json` 承接和字段物化生命周期。
- `edera-cli`: 增加普通 EntityType 字段物化的维护命令。

## Impact

- 影响 EntityType metadata、EntityStore routing、table manager、DDL generation、repository 查询路径。
- 影响 Alembic/SQLite 迁移策略，但不要求每次普通字段新增都立即创建 migration。
- 影响 CLI/gRPC/Web Console 的字段物化、deprecated 字段展示和维护操作。
- 依赖 `db-backed-core-entities` 完成 DB source-of-truth 基础；不应先于第一阶段实施。
