## ADDED Requirements

### Requirement: List entity types

系统 SHALL 提供 `GET /api/config/entity-types` 端点，返回所有已定义的 entity type 列表。

#### Scenario: List all types

- **WHEN** 前端请求 `GET /api/config/entity-types`
- **THEN** 系统 SHALL 返回 `{ "types": { "<name>": { display_name, business_id_field, ... }, ... } }` 格式的响应

### Requirement: Read single entity type

系统 SHALL 提供 `GET /api/config/entity-types/{name}` 端点，返回指定类型的完整 YAML 内容。

#### Scenario: Read existing type

- **WHEN** 前端请求 `GET /api/config/entity-types/stock`
- **THEN** 系统 SHALL 返回 `{ "name": "stock", "content": "<yaml text>" }` 格式的响应

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

系统 SHALL 提供 `PUT /api/config/entity-types/{name}` 端点，更新已有的 entity type 定义。

#### Scenario: Update valid type

- **WHEN** 前端提交合法的 YAML content
- **THEN** 系统 SHALL 覆写对应文件，并返回更新成功状态

#### Scenario: Update with invalid content

- **WHEN** 前端提交不符合 EntityTypeConfig schema 的 content
- **THEN** 系统 MUST 返回 400 错误，包含校验错误信息

### Requirement: Delete entity type

系统 SHALL 提供 `DELETE /api/config/entity-types/{name}` 端点，删除 entity type 定义。

#### Scenario: Delete type without instances

- **WHEN** 前端请求删除且该类型下无实例
- **THEN** 系统 SHALL 删除 `schemas/entity-types/{name}.yaml` 文件

#### Scenario: Delete type with instances (no cascade)

- **WHEN** 前端请求删除且该类型下存在实例，未传 `cascade=true`
- **THEN** 系统 MUST 返回 409 错误，包含 `{ "instance_count": N }` 信息

#### Scenario: Delete type with cascade

- **WHEN** 前端请求 `DELETE /api/config/entity-types/{name}?cascade=true`
- **THEN** 系统 SHALL 先删除该类型所有实例及相关关系，再删除类型定义文件
