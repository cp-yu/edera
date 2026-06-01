# entity-relation-crud-api Specification

## Purpose
此规约记录变更 entity-config-page 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Relation UUID identification

系统 SHALL 为每条 entity relation 分配唯一 UUID ID，存储在 `entity-relations.yaml` 中。

#### Scenario: Load relations with existing IDs

- **WHEN** 系统加载 `entity-relations.yaml` 且关系已有 `id` 字段
- **THEN** 系统 SHALL 使用已有 ID

#### Scenario: Auto-assign IDs to legacy relations

- **WHEN** 系统加载 `entity-relations.yaml` 且某条关系缺少 `id` 字段
- **THEN** 系统 SHALL 自动生成 UUID 并补全，持久化回文件

### Requirement: List entity relations

系统 SHALL 提供 `GET /api/entity-relations` 端点，以 `{ "relations": [...] }` 包装格式返回所有关系，每条包含 `id`、`entities`、`type`、`metadata`。关系查询通过 `type=relation` 表达式路由到 `_query_relations`。

#### Scenario: List all relations

- **WHEN** 前端请求 `GET /api/entity-relations`
- **THEN** 系统 SHALL 以 `{ "relations": [...] }` 格式返回所有关系，每条包含 `id`、`entities`、`type`、`metadata`

#### Scenario: List relation types

- **WHEN** 前端请求 `GET /api/entity-relations/types`
- **THEN** 系统 SHALL 以 `{ "types": [...] }` 格式返回所有已使用的关系类型去重列表，从 `attributes.relation_type` 提取

### Requirement: Create entity relation

系统 SHALL 提供 `POST /api/entity-relations` 端点，创建单条关系。

#### Scenario: Create valid relation

- **WHEN** 前端提交 `{ "entities": ["stock:00700.HK", "web-source:sample-web"], "type": "uses-source" }`
- **THEN** 系统 SHALL 生成 UUID ID，验证引用的实体存在，持久化到 `entity-relations.yaml`

#### Scenario: Create with non-existent entity

- **WHEN** 前端提交的 `entities` 中包含不存在的实体引用
- **THEN** 系统 MUST 返回 400 错误 "Entity not found: <ref>"

#### Scenario: Create duplicate relation

- **WHEN** 前端提交的关系（相同 entities + type）已存在
- **THEN** 系统 MUST 返回 409 conflict 错误

### Requirement: Delete entity relation

系统 SHALL 提供 `DELETE /api/entity-relations/{id}` 端点，删除单条关系。

#### Scenario: Delete existing relation

- **WHEN** 前端请求 `DELETE /api/entity-relations/{id}`
- **THEN** 系统 SHALL 从 `entity-relations.yaml` 中移除该条关系

#### Scenario: Delete non-existent relation

- **WHEN** 前端请求删除不存在的 ID
- **THEN** 系统 MUST 返回 404 错误

