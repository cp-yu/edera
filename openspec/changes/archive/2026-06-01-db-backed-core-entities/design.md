## Context

Edera 已有统一 Entity 模型、SQLite/WAL 数据库、输出型 Entity 的 `node_outputs` 表，以及 runtime facts 表。当前割裂点是核心配置型 Entity 仍由 YAML/config 文件驱动，`EntityStore` 的数据库路由也没有覆盖 server 侧完整 CRUD 与 runtime snapshot。新目标是让 DB 成为 `node`、`dag`、`trigger`、`resource` 的唯一运行时 source of truth，YAML 只保留为 CLI import/export/template 格式。

## Goals / Non-Goals

**Goals:**
- 将 `node`、`dag`、`trigger`、`resource` 迁移为固定 per-type tables，并按当前核心模型完全列化。
- 让 `EntityService`、CLI、Web Console、runtime snapshot 都从 DB 读取核心配置型 Entity。
- 支持完整 Entity 文档格式的 YAML `import`、`export`、`template`。
- 明确 runtime 状态边界：运行中状态在内存，提交事实落 SQLite runtime tables。
- raw stdout/stderr 等大体积日志文件落盘，DB 仅保存索引。

**Non-Goals:**
- 不实现普通 EntityType 的 lazy materialization。
- 不把输出型 Entity 合并进核心配置表。
- 不引入 Postgres 或独立 log DB。
- 不在第一阶段设计核心类型的动态字段演进。

## Decisions

1. DB 是核心配置型 Entity 的唯一运行时 source of truth。
   YAML 文件只用于 `edera entity import/export/template --file`。这样避免 DB 与文件双真相，也让 Web Console 审查可以围绕 DB 状态进行。

2. 核心类型使用固定 per-type tables 并完全列化。
   `entity_node`、`entity_dag`、`entity_trigger`、`entity_resource` 按当前模型建列，`attributes_json` 只能作为兼容扩展槽，核心读取路径不得依赖它。这样牺牲未来字段随意变化能力，换取引擎读取和查询的确定性。

3. 输出型 Entity 继续独立。
   `node_outputs` 保留 run/node/retention/tags 语义，不与配置型 Entity 混表。

4. runtime facts 是提交事实，不是运行中状态机。
   DAG runner、trigger executor、resource scheduler 消费 committed runtime snapshot 的内存对象；`dag_runs`、`node_runs`、`edge_inputs`、`source_recoveries`、`emit_records` 只负责持久化事实和查询投影。

5. YAML 模板使用完整 Entity 文档格式。
   `template -> edit -> import -> export` 使用同一结构：`type`、`id`、`attributes`。CLI 不维护 attributes-only 的第二套文件格式。

## Risks / Trade-offs

- [Migration drift] → 迁移必须保留 UUID、business_id 和引用关系；迁移完成后运行时不得回读 YAML。
- [Schema rigidity] → 核心类型完全列化后字段变化需要单独 migration/change；这是核心模型稳定性的代价。
- [Snapshot consistency] → DB 写入配置后必须构建 committed snapshot，再替换运行视图；失败 reload 保留旧 snapshot。
- [CLI format ambiguity] → import/export/template 统一完整 Entity 文档格式，减少特殊规则。
- [Log volume] → raw logs 不写入 runtime facts 表，只写文件并记录 `log_index`。

## Migration Plan

1. 新增 Alembic migration 创建 `entity_types`、`entity_node`、`entity_dag`、`entity_trigger`、`entity_resource`、`log_index`。
2. 编写迁移流程导入现有 `config/nodes/*.yaml`、`config/dags/*.yaml`、`config/triggers/*.yaml` 和 resource 实例。
3. 切换 EntityService/EntityStore/RuntimeSnapshotBuilder 到 DB。
4. 保留 YAML import/export/template 命令，但运行时 loader 不再读取 YAML。
5. 回滚策略为保留迁移前 YAML 备份和 DB export；回滚不自动双写。
