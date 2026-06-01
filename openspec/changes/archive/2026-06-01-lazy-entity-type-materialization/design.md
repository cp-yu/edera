## Context

第一阶段将核心 `node`、`dag`、`trigger`、`resource` 固定列化并迁入 DB。普通 EntityType 仍需要在类型增减、字段变化和查询性能之间取得平衡。立即为每次字段变化执行 DDL 会扩大 SQLite migration 风险，因此普通类型采用 per-type table + `attributes_json` 承接 + lazy materialization。

## Goals / Non-Goals

**Goals:**
- 普通 EntityType 使用 `entity_<type>` per-type table。
- 新增或未知字段先写入 `attributes_json`。
- 稳定、高频或显式 indexed 字段可 lazy materialize 为真实列。
- 支持 deprecated fields 生命周期和维护命令。

**Non-Goals:**
- 不改变第一阶段核心类型固定列化表。
- 不合并输出型 Entity。
- 不改变 runtime facts 的内存边界。

## Decisions

1. 普通类型也一型一表。  
   这与核心类型保持表边界一致，但普通类型不立即全字段列化。

2. `attributes_json` 是新增字段缓冲区。  
   字段新增先不触发 DDL，避免每次 schema 修改都产生 migration。

3. 字段物化是显式维护动作。  
   只有稳定、高频或被声明 indexed 的字段才物化为列；物化要记录 metadata 并回填历史数据。

4. 字段删除先 deprecated。  
   删除字段不立即 drop column；系统停止读写该字段，后续维护窗口清理。

## Risks / Trade-offs

- [DDL drift] → 所有物化字段记录在 EntityType metadata，并提供检查命令。
- [Query ambiguity] → 查询 planner 先查 materialized columns，再回退 `attributes_json`。
- [Phase coupling] → 本 change 必须依赖 DB source-of-truth 基础，不先于 `db-backed-core-entities` 实施。
