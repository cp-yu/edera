# entity-instance-crud-api Specification

## Purpose
此规约记录变更 entity-config-page 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: List entity instances

系统 SHALL 提供 `GET /api/entities` 端点，返回所有实例及其 display 信息。

#### Scenario: List all instances

- **WHEN** 前端请求 `GET /api/entities`
- **THEN** 系统 SHALL 返回所有实例，每个实例包含 `id`、`type`、`ref`、`display`、`attributes`

#### Scenario: Filter by type

- **WHEN** 前端请求 `GET /api/entities?type=stock`
- **THEN** 系统 SHALL 仅返回 `type` 为 `stock` 的实例

### Requirement: Create entity instance

系统 SHALL 提供 `POST /api/entities` 端点，创建单个实体实例，ID 自动生成 UUID。

#### Scenario: Create valid instance

- **WHEN** 前端提交 `{ "type": "stock", "attributes": { "code": "09988.HK", "name": "Alibaba" } }`
- **THEN** 系统 SHALL 生成 UUID 作为 ID，验证 attributes 符合类型 schema，持久化到 `entities.yaml`，并返回创建的实例

#### Scenario: Create with unknown type

- **WHEN** 前端提交的 `type` 在 entity types 中不存在
- **THEN** 系统 MUST 返回 400 错误 "unknown entity type: <type>"

#### Scenario: Create with invalid attributes

- **WHEN** 前端提交的 `attributes` 不符合类型 schema（如缺少 required 字段）
- **THEN** 系统 MUST 返回 400 错误，包含校验错误信息

#### Scenario: Create with duplicate business ID

- **WHEN** 前端提交的实例 business ID 与已有实例重复
- **THEN** 系统 MUST 返回 400 错误 "duplicate entity business ref"

### Requirement: Update entity instance

系统 SHALL 提供 `PUT /api/entities/{id}` 端点，更新单个实体实例的 attributes。

#### Scenario: Update valid instance

- **WHEN** 前端提交合法的 attributes
- **THEN** 系统 SHALL 通过 `EntityStore.save()` 更新实例，尊重 `field_permissions`

#### Scenario: Update non-existent instance

- **WHEN** 前端提交的 ID 不存在
- **THEN** 系统 MUST 返回 404 错误

#### Scenario: Update read-only field

- **WHEN** 前端提交的 attributes 包含 `read-only` 字段的修改
- **THEN** 系统 SHALL 忽略该字段的修改，保留原值

### Requirement: Delete entity instance

系统 SHALL 提供 `DELETE /api/entities/{id}` 端点，删除单个实体实例并级联删除相关关系。

#### Scenario: Delete instance

- **WHEN** 前端请求删除某实例
- **THEN** 系统 SHALL 从 `entities.yaml` 中移除该实例，并从 `entity-relations.yaml` 中移除所有引用该实例的关系

#### Scenario: Delete non-existent instance

- **WHEN** 前端请求删除不存在的 ID
- **THEN** 系统 MUST 返回 404 错误

#### Scenario: Return deleted relation count

- **WHEN** 删除实例时存在关联关系
- **THEN** 系统 SHALL 在响应中包含 `{ "deleted": true, "relations_removed": N }`

### Requirement: Entity 写操作 emit 事件

系统 SHALL 在 Entity 的 Create/Update/Delete 操作完成后自动 emit `event:entity-changed:{ref}` 事件。

#### Scenario: Entity 创建 emit

- **WHEN** 通过 `EntityService.Create` 创建一个 entity，ref 为 `stock:00700.HK`
- **THEN** 系统调用 `emit("event:entity-changed:stock:00700.HK")`

#### Scenario: Entity 更新 emit

- **WHEN** 通过 `EntityService.Update` 修改一个 entity 的 attributes
- **THEN** 系统调用 `emit("event:entity-changed:{ref}")`

#### Scenario: Entity 删除 emit

- **WHEN** 通过 `EntityService.Delete` 删除一个 entity
- **THEN** 系统调用 `emit("event:entity-changed:{ref}")`

