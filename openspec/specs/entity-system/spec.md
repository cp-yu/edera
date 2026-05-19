# entity-system Specification

## Purpose
此规约记录变更 refactor-to-domain-agnostic-entity-system 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 实体类型定义

系统 SHALL 支持通过 YAML 文件定义可扩展的实体类型，每个类型包含 schema、业务 ID 字段、显示模板和字段权限。

#### Scenario: 定义股票实体类型

- **WHEN** 用户创建 `schemas/entity-types/stock.yaml` 文件，包含 `display_name`, `business_id_field`, `display_template`, `schema`, `field_permissions` 字段
- **THEN** 系统加载该类型定义，并在创建 `type: stock` 的实体时验证 attributes

#### Scenario: 字段权限黑名单

- **WHEN** 实体类型定义中 `field_permissions` 声明 `code: read-only`
- **THEN** 节点默认只能读取 `code` 字段，不能修改

#### Scenario: 未声明字段默认可读写

- **WHEN** 实体类型定义中 `field_permissions` 未声明 `holding` 字段
- **THEN** 节点可以读取和修改 `holding` 字段

### Requirement: 实体存储

系统 SHALL 支持在 `config/entities.yaml` 中存储所有类型的实体，每个实体包含 UUID、类型和自由的 attributes。

#### Scenario: 创建股票实体

- **WHEN** 用户在 `entities.yaml` 中添加实体，包含 `id` (UUID), `type: stock`, `attributes: {code, name, holding}`
- **THEN** 系统加载该实体，并可通过 UUID 或业务 ID 引用

#### Scenario: 创建信息源实体

- **WHEN** 用户在 `entities.yaml` 中添加实体，包含 `id` (UUID), `type: rss-source`, `attributes: {name, url}`
- **THEN** 系统加载该实体，信息源不再是独立概念

#### Scenario: 实体类型验证

- **WHEN** 实体的 `type` 对应的类型定义设置 `validate: true`
- **THEN** 系统验证 `attributes` 是否符合 schema，不符合时报错

### Requirement: 实体引用解析

系统 SHALL 支持通过 UUID 或业务 ID 引用实体，业务 ID 格式为 `type:business_id`。

#### Scenario: UUID 引用

- **WHEN** 节点配置中使用 `entities: ["550e8400-e29b-41d4-a716-446655440000"]`
- **THEN** 系统通过 UUID 查找实体

#### Scenario: 业务 ID 引用

- **WHEN** 节点配置中使用 `entities: ["stock:00700.HK"]`
- **THEN** 系统根据 `stock` 类型的 `business_id_field` (code) 查找 `attributes.code = "00700.HK"` 的实体

#### Scenario: 引用不存在的实体

- **WHEN** 节点配置中引用的实体不存在
- **THEN** 系统在配置保存时报错，提示实体不存在

### Requirement: 字段权限检查

系统 SHALL 在节点执行时检查字段读写权限，违反权限时发出警告并阻止操作。

#### Scenario: 读取受保护字段

- **WHEN** 节点尝试读取 `field_permissions` 设置为 `none` 的字段
- **THEN** 系统发出警告 "Permission denied: <field> is not readable"，返回 None

#### Scenario: 修改只读字段

- **WHEN** 节点尝试修改 `field_permissions` 设置为 `read-only` 的字段
- **THEN** 系统发出警告 "Permission denied: <field> is read-only"，不保存修改

#### Scenario: 正常读写

- **WHEN** 节点读写未声明权限的字段（默认 `read-write`）
- **THEN** 系统允许操作

### Requirement: 节点实例提权

系统 SHALL 支持节点实例通过 `entity_permissions` 配置覆盖默认字段权限，只能提权不能降权。

#### Scenario: 提权修改只读字段

- **WHEN** 节点配置 `entity_permissions: {stock: {code: read-write}}`，而默认权限是 `read-only`
- **THEN** 该节点实例可以修改 `code` 字段

#### Scenario: 提权读取受保护字段

- **WHEN** 节点配置 `entity_permissions: {stock: {internal_notes: read-only}}`，而默认权限是 `none`
- **THEN** 该节点实例可以读取 `internal_notes` 字段

#### Scenario: 尝试降权

- **WHEN** 节点配置 `entity_permissions: {stock: {holding: read-only}}`，而默认权限是 `read-write`
- **THEN** 系统在配置保存时报错，提示不能降权

### Requirement: 节点上下文实体访问

系统 SHALL 在节点执行时提供实体访问接口，支持读取和保存实体。

#### Scenario: 读取实体

- **WHEN** 节点调用 `context.get_entity("stock:00700.HK")`
- **THEN** 系统返回对应的实体对象，包含 `id`, `type`, `attributes`

#### Scenario: 保存实体

- **WHEN** 节点修改实体的 `attributes` 后调用 `context.save_entity(entity)`
- **THEN** 系统检查权限，保存允许修改的字段，忽略受保护字段

#### Scenario: 创建新实体

- **WHEN** 节点调用 `context.create_entity(type="stock", attributes={...})`
- **THEN** 系统生成 UUID，验证 attributes，保存到 `entities.yaml`

