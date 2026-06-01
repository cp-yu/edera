## ADDED Requirements

### Requirement: Entity table DDL namespace compatibility

系统 SHALL 保证普通 EntityType per-type tables 与 extension declarative storage 表命名互不冲突。EntityType 表 MUST 使用 `entity_` 前缀，extension 表 MUST 继续使用 `ext_` 前缀。

#### Scenario: Entity and extension table names do not collide
- **WHEN** 普通 EntityType `rss-source` 创建 `entity_rss_source`
- **AND** 扩展 `rss-fetcher` 声明表 `raw_items`
- **THEN** 系统 SHALL 保持扩展表名为 `ext_rss_fetcher_raw_items`
- **AND** 两类表 MUST NOT 共享相同实际表名

### Requirement: Shared column type contract

系统 SHALL 复用 declarative storage 支持的列类型集合来描述普通 EntityType materialized fields，包括 `integer`、`text`、`real`、`datetime`、`boolean` 和 `json`。

#### Scenario: Reject unsupported materialized field type
- **WHEN** 普通 EntityType 声明 materialized field 类型为 `blob`
- **THEN** 系统 MUST 拒绝该字段物化声明
