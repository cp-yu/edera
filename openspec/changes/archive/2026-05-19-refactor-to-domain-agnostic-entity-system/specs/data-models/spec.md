## MODIFIED Requirements

### Requirement: RawItem 数据模型

系统 SHALL 定义 RawItem 模型存储采集的原始条目，MUST 包含：url（唯一标识）、title、content、source_name、source_type、tags（关联实体引用列表）、published_at、fetched_at。

#### Scenario: 创建 RawItem 记录

- **WHEN** 采集节点抓取到一条新信息
- **THEN** 系统创建 RawItem 记录，所有必填字段均有值，url 作为去重唯一标识

#### Scenario: URL 去重

- **WHEN** 采集节点尝试创建一条已存在 url 的 RawItem
- **THEN** 系统跳过该条目，不创建重复记录

#### Scenario: Store entity tags

- **WHEN** 系统保存 RawItem 到数据库
- **THEN** 系统 SHALL 将关联的实体引用存储在 `tags` 字段（如 `["stock:00700.HK", "city:北京"]`）

#### Scenario: Query by entity tag

- **WHEN** 系统查询特定实体的 RawItem
- **THEN** 系统 SHALL 通过 `tags` 字段过滤（如 `WHERE "stock:00700.HK" = ANY(tags)`）

#### Scenario: Migrate from stock_codes

- **WHEN** 系统从旧数据库迁移
- **THEN** 系统 SHALL 将 `stock_codes` 中的值转换为 `tags`（如 `["00700.HK"]` → `["stock:00700.HK"]`）
