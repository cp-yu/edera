# entity-system Specification

## Purpose
此规约记录变更 refactor-to-domain-agnostic-entity-system 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 实体类型定义

系统 SHALL 支持通过 YAML 文件定义可扩展的实体类型，每个类型包含 schema、业务 ID 字段、显示模板、字段权限和存储层级声明。EntityType schema 中特定字段的存在 MUST 作为能力声明。

#### Scenario: 定义 Node EntityType

- **WHEN** 用户创建 `config/schemas/node.yaml` 文件，schema 中包含 `handler`、`input_type`、`output_type` 字段定义
- **THEN** 系统加载该类型定义，识别包含 `handler` 字段的 Entity 为可执行节点

#### Scenario: 定义 DAG EntityType

- **WHEN** 用户创建 `config/schemas/dag.yaml` 文件，schema 中包含 `edges`、`nodes` 字段定义
- **THEN** 系统加载该类型定义，识别包含 `edges` 字段的 Entity 为 DAG

#### Scenario: 定义 Trigger EntityType

- **WHEN** 用户创建 `config/schemas/trigger.yaml` 文件，schema 中包含 `wait_for`、`target` 字段定义
- **THEN** 系统加载该类型定义，识别包含 `wait_for` 字段的 Entity 为 Trigger

#### Scenario: 存储层级声明

- **WHEN** EntityType 定义中包含 `storage_tier: database`
- **THEN** 系统将该类型的所有 Entity 实例存储在数据库层

#### Scenario: 字段权限黑名单

- **WHEN** 实体类型定义中 `field_permissions` 声明 `code: read-only`
- **THEN** 节点默认只能读取 `code` 字段，不能修改

### Requirement: 实体存储

系统 SHALL 支持在对应存储层存储所有类型的实体。配置型 Entity 存储在 `config/` 对应职能目录，输出型存储在数据库，瞬态型存储在内存。

#### Scenario: 创建 Node Entity

- **WHEN** 用户创建一个 `type: node` 的 Entity
- **THEN** 系统将其持久化到 `config/nodes/` 目录下的 YAML 文件

#### Scenario: 创建输出型 Entity

- **WHEN** Node 执行产出一个 `type: analysis` 的 Entity
- **THEN** 系统将其存储到数据库 `node_outputs` 表

#### Scenario: 实体类型验证

- **WHEN** 实体的 `type` 对应的类型定义设置 `validate: true`
- **THEN** 系统验证 `attributes` 是否符合 schema，不符合时报错

### Requirement: 实体引用解析

系统 SHALL 支持通过 UUID 或业务 ID 引用实体，业务 ID 格式为 `type:business_id`。引用解析 MUST 跨存储层透明工作。

#### Scenario: UUID 引用

- **WHEN** 节点配置中使用 UUID 引用
- **THEN** 系统通过 UUID 在所有存储层查找实体

#### Scenario: 业务 ID 引用

- **WHEN** 节点配置中使用 `"stock:00700.HK"` 引用
- **THEN** 系统根据 `stock` 类型的 `business_id_field` 查找对应实体

#### Scenario: 跨存储层引用

- **WHEN** 一个配置型 Entity 引用一个输出型 Entity
- **THEN** 系统透明地从数据库层解析该引用

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

系统 SHALL 在节点执行时提供实体访问接口，支持读取和保存实体。接口 MUST 通过统一的 Entity Store 实现。

#### Scenario: 读取实体

- **WHEN** 节点调用 `context.get_entity("stock:00700.HK")`
- **THEN** 系统通过 Entity Store 返回对应的实体对象

#### Scenario: 保存实体

- **WHEN** 节点修改实体的 `attributes` 后调用 `context.save_entity(entity)`
- **THEN** 系统检查权限，保存到对应存储层

#### Scenario: 创建新实体

- **WHEN** 节点调用 `context.create_entity(type="analysis", attributes={...})`
- **THEN** 系统根据 EntityType 的 `storage_tier` 决定存储位置，生成 UUID，校验后保存

