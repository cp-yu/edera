## MODIFIED Requirements

### Requirement: RawItem tags field

`RawItem` 模型 SHALL 使用通用的 `tags` 字段替代 `stock_codes` 字段，支持任意实体引用。

#### Scenario: Store entity tags

- **WHEN** 系统保存 RawItem 到数据库
- **THEN** 系统 SHALL 将关联的实体引用存储在 `tags` 字段（如 `["stock:00700.HK", "city:北京"]`）

#### Scenario: Query by entity tag

- **WHEN** 系统查询特定实体的 RawItem
- **THEN** 系统 SHALL 通过 `tags` 字段过滤（如 `WHERE "stock:00700.HK" = ANY(tags)`）

#### Scenario: Migrate from stock_codes

- **WHEN** 系统从旧数据库迁移
- **THEN** 系统 SHALL 将 `stock_codes` 中的值转换为 `tags`（如 `["00700.HK"]` → `["stock:00700.HK"]`）
