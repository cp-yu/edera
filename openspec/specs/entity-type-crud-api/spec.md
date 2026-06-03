---
capabilities:
  - cap.entity-type-crud-api
---
# entity-type-crud-api Specification

## Purpose
定义 List entity types、Read single entity type、Create entity type、Update entity type等能力。
## Requirements
### Requirement: List entity types

系统 SHALL 提供 `GET /api/config/entity-types` 端点，返回所有已定义的 entity type 列表。

#### Scenario: List all types

- **WHEN** 前端请求 `GET /api/config/entity-types`
- **THEN** 系统 SHALL 返回 `{ "types": { "<name>": { display_name, business_id_field, ... }, ... } }` 格式的响应

### Requirement: Read single entity type

系统 SHALL 提供 `GET /api/config/entity-types/{name}` 端点，返回指定类型的完整 YAML 内容。系统 SHALL 同时搜索 `schemas/entity-types/` 和 `config/schemas/` 两个目录。

#### Scenario: Read existing type from schemas/entity-types

- **WHEN** 前端请求 `GET /api/config/entity-types/stock`
- **THEN** 系统 SHALL 返回 `{ "name": "stock", "content": "<yaml text>" }` 格式的响应

#### Scenario: Read existing type from config/schemas

- **WHEN** 前端请求 `GET /api/config/entity-types/node`
- **THEN** 系统 SHALL 返回 `{ "name": "node", "content": "<yaml text>" }` 格式的响应

#### Scenario: Read non-existent type

- **WHEN** 前端请求 `GET /api/config/entity-types/unknown`
- **THEN** 系统 MUST 返回 404 错误

### Requirement: Create entity type

系统 SHALL 提供 `POST /api/config/entity-types` 端点，创建新的 entity type 定义文件。

#### Scenario: Create valid type

- **WHEN** 前端提交 `{ "name": "etf", "content": "<valid yaml>" }`
- **THEN** 系统 SHALL 写入 `schemas/entity-types/etf.yaml`，并返回创建成功状态

#### Scenario: Create duplicate type

- **WHEN** 前端提交的 name 已存在
- **THEN** 系统 MUST 返回 409 conflict 错误

#### Scenario: Create with invalid YAML

- **WHEN** 前端提交的 content 不符合 EntityTypeConfig schema
- **THEN** 系统 MUST 返回 400 错误，包含校验错误信息

### Requirement: Update entity type

系统 SHALL 提供 `PUT /api/config/entity-types/{name}` 端点，更新已有的 entity type 定义。系统 MUST 拒绝对 `system_protected: true` 类型的更新操作。

#### Scenario: Update valid type

- **WHEN** 前端提交合法的 YAML content 到非 protected 类型
- **THEN** 系统 SHALL 覆写对应文件，并返回更新成功状态

#### Scenario: Update with invalid content

- **WHEN** 前端提交不符合 EntityTypeConfig schema 的 content
- **THEN** 系统 MUST 返回 400 错误，包含校验错误信息

#### Scenario: Update protected type

- **WHEN** 前端请求 `PUT /api/config/entity-types/node`，且 `node` 类型的 `system_protected` 为 `true`
- **THEN** 系统 MUST 返回 403 错误，message 为 `entity type 'node' is system protected`

### Requirement: Delete entity type

系统 SHALL 提供 `DELETE /api/config/entity-types/{name}` 端点，删除 entity type 定义。系统 MUST 拒绝对 `system_protected: true` 类型的删除操作。

#### Scenario: Delete type without instances

- **WHEN** 前端请求删除非 protected 类型且该类型下无实例
- **THEN** 系统 SHALL 删除 `schemas/entity-types/{name}.yaml` 文件

#### Scenario: Delete type with instances (no cascade)

- **WHEN** 前端请求删除且该类型下存在实例，未传 `cascade=true`
- **THEN** 系统 MUST 返回 409 错误，包含 `{ "instance_count": N }` 信息

#### Scenario: Delete type with cascade

- **WHEN** 前端请求 `DELETE /api/config/entity-types/{name}?cascade=true`，且类型非 protected
- **THEN** 系统 SHALL 按顺序持久化删除该类型所有实例、相关关系和类型定义文件，但 MUST NOT 承诺跨文件原子性；中间步骤失败时已完成写入不会自动回滚

#### Scenario: Delete protected type

- **WHEN** 前端请求 `DELETE /api/config/entity-types/node`，且 `node` 类型的 `system_protected` 为 `true`
- **THEN** 系统 MUST 返回 403 错误，message 为 `entity type 'node' is system protected`

### Requirement: Cascade delete 降低事务性承诺
系统 SHALL 在 `DELETE /api/config/entity-types/{name}?cascade=true` 时按顺序删除类型、实例、关系，但 MUST NOT 保证跨文件原子性。中间步骤失败时 SHALL 返回错误，但已完成的写入不会自动回滚。

#### Scenario: Cascade delete 顺序持久化
- **WHEN** 前端请求 cascade delete entity type
- **THEN** 系统 SHALL 依次保存 entities.yaml（删除实例）、entity-relations.yaml（删除关系）、删除 type 文件，任一步骤失败则返回错误

#### Scenario: 中间步骤失败不回滚
- **WHEN** cascade delete 过程中第二步失败
- **THEN** 系统 SHALL 返回错误，但第一步的文件修改已持久化，不会自动恢复
