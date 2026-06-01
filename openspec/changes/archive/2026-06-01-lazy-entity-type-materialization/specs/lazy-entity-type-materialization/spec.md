## ADDED Requirements

### Requirement: 普通 EntityType per-type table

系统 SHALL 为普通 EntityType 创建独立 `entity_<type>` 表。普通类型表 MUST 包含 `id`、`business_id`、`schema_version`、`attributes_json`、`created_at` 和 `updated_at`，并 MAY 包含 materialized columns。

#### Scenario: Create ordinary entity type table
- **WHEN** 用户创建普通 EntityType `stock`
- **THEN** 系统 SHALL 创建或注册 `entity_stock` 表
- **AND** 表 SHALL 包含通用列和 `attributes_json`

#### Scenario: Core tables unchanged
- **WHEN** 普通 EntityType 表创建
- **THEN** 系统 MUST NOT 修改 `entity_node`、`entity_dag`、`entity_trigger` 或 `entity_resource` 的固定列化表语义

### Requirement: 新增字段进入 attributes_json

系统 SHALL 将普通 EntityType 的新增、未知或未物化字段写入 `attributes_json`。系统 MUST NOT 因普通字段新增立即执行 DDL。

#### Scenario: Store new field in attributes_json
- **WHEN** `stock` EntityType 新增字段 `sector`
- **THEN** 系统 SHALL 接受该字段并写入 `entity_stock.attributes_json`
- **AND** 系统 MUST NOT 立即 ALTER TABLE 添加 `sector` 列

### Requirement: Lazy materialization

系统 SHALL 支持将普通 EntityType 中稳定、高频或显式声明 indexed 的字段 lazy materialize 为真实列。物化 MUST 更新 EntityType metadata，并回填已有 Entity 数据。

#### Scenario: Materialize indexed field
- **WHEN** `stock.code` 被声明为 indexed/materialized
- **THEN** 系统 SHALL 创建或确认 `entity_stock.code` 列和索引
- **AND** 系统 SHALL 从 `attributes_json` 回填历史数据

#### Scenario: Query materialized field
- **WHEN** 用户查询已物化字段 `stock.code`
- **THEN** 系统 SHALL 优先使用真实列执行查询

### Requirement: Deprecated field lifecycle

系统 SHALL 支持将普通 EntityType 字段标记为 deprecated。deprecated 字段 MUST 停止新写入，MAY 保留既有列，直到维护窗口执行清理。

#### Scenario: Stop using deprecated field
- **WHEN** `stock.legacy_code` 被标记为 deprecated
- **THEN** 系统 SHALL 停止在新写入中填充该字段
- **AND** 系统 MUST NOT 要求立即 drop column

#### Scenario: Cleanup deprecated column
- **WHEN** 维护命令确认 deprecated 字段已不再被访问
- **THEN** 系统 MAY 在维护窗口清理对应列
