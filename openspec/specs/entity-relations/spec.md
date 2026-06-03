---
capabilities:
  - cap.entity-relation-crud-api
---
# entity-relations Specification

## Purpose
定义 实体关系定义、节点自动发现实体、节点配置优先、关系查询 API。
## Requirements
### Requirement: 实体关系定义

系统 SHALL 支持以 DB-backed relation Entity 定义实体之间的无方向关系，每个关系包含实体列表、类型和可选的元数据。YAML 仅作为 import/export/template 格式。

#### Scenario: 定义股票和信息源的关系

- **WHEN** 用户创建 relation Entity，包含 `entities: ["stock:00700.HK", "rss-source:sample-rss"]`, `type: uses-source`
- **THEN** 系统加载该关系，可用于自动发现和 UI 可视化

#### Scenario: 关系类型自由定义

- **WHEN** 用户使用任意字符串作为关系 `type`（如 `uses-source`, `depends-on`, `related-to`）
- **THEN** 系统接受该类型，不需要预先声明

#### Scenario: 关系元数据

- **WHEN** 用户在关系中添加 `metadata: {priority: high, created_at: "2026-05-18"}`
- **THEN** 系统保存元数据，可用于排序或过滤

### Requirement: 节点自动发现实体

系统 SHALL 在节点配置只指定 source 而未指定 entities 时，自动从 DB-backed relation Entity Store 发现关联的实体。

#### Scenario: 自动发现关联实体

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss"}`，未指定 `entities`
- **THEN** 系统查找 DB-backed relation Entity Store 中包含该 source 的关系，返回关联的其他实体（如 `stock:00700.HK`）

#### Scenario: 无关联关系时返回空

- **WHEN** 节点配置的 source 在 DB-backed relation Entity Store 中没有关联关系
- **THEN** 系统返回空列表，节点处理所有数据

### Requirement: 节点配置优先

系统 SHALL 在节点配置显式指定 entities 时，使用节点配置而忽略 relation Entity Store 的自动发现。

#### Scenario: 显式配置覆盖自动发现

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss", entities: ["stock:600519.SH"]}`
- **THEN** 系统使用 `stock:600519.SH`，忽略 relation Entity Store 中该 source 的其他关联实体

#### Scenario: 空列表禁用自动发现

- **WHEN** 节点配置 `config: {source: "rss-source:sample-rss", entities: []}`
- **THEN** 系统不处理任何实体，即使 relation Entity Store 中有关联关系

### Requirement: 关系查询 API

系统 SHALL 提供 API 查询实体的关联关系，支持按实体 ID 和关系类型过滤。

#### Scenario: 查询实体的所有关系

- **WHEN** 调用 `GET /api/entity-relations?entity=stock:00700.HK`
- **THEN** 系统返回包含该实体的所有关系

#### Scenario: 按关系类型过滤

- **WHEN** 调用 `GET /api/entity-relations?entity=stock:00700.HK&type=uses-source`
- **THEN** 系统只返回 `type: uses-source` 的关系

#### Scenario: 查询关联的其他实体

- **WHEN** 调用 `GET /api/entity-relations?entity=stock:00700.HK&type=uses-source`
- **THEN** 系统返回关系中除 `stock:00700.HK` 外的其他实体（如 `rss-source:sample-rss`）
