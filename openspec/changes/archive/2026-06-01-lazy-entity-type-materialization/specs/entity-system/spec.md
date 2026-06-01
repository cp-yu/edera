## MODIFIED Requirements

### Requirement: 实体类型定义

系统 SHALL 支持通过 DB-backed EntityType metadata 定义可扩展的实体类型，每个类型包含 schema、业务 ID 字段、显示模板、字段权限、存储层级声明、schema version、table mapping、materialized fields 和 deprecated fields。EntityType schema 中特定字段的存在 MUST 作为能力声明。

#### Scenario: 定义 Node EntityType

- **WHEN** 系统注册 `node` EntityType，schema 中包含 `handler`、`input_type`、`output_type` 字段定义
- **THEN** 系统加载该类型定义，识别包含 `handler` 字段的 Entity 为可执行节点

#### Scenario: 定义 DAG EntityType

- **WHEN** 系统注册 `dag` EntityType，schema 中包含 `edges`、`nodes` 字段定义
- **THEN** 系统加载该类型定义，识别包含 `edges` 字段的 Entity 为 DAG

#### Scenario: 定义 Trigger EntityType

- **WHEN** 系统注册 `trigger` EntityType，schema 中包含 `wait_for`、`target` 字段定义
- **THEN** 系统加载该类型定义，识别包含 `wait_for` 字段的 Entity 为 Trigger

#### Scenario: 存储层级声明

- **WHEN** EntityType 定义中包含 `storage_tier: database`
- **THEN** 系统将该类型的所有 Entity 实例存储在数据库层

#### Scenario: 字段权限黑名单

- **WHEN** 实体类型定义中 `field_permissions` 声明 `code: read-only`
- **THEN** 节点默认只能读取 `code` 字段，不能修改

#### Scenario: Materialized fields metadata

- **WHEN** 普通 EntityType 将字段 `code` 声明为 materialized
- **THEN** 系统 SHALL 在 EntityType metadata 中记录该字段、列类型和索引意图

### Requirement: 实体存储

系统 SHALL 支持在对应存储层存储所有类型的实体。核心配置型 Entity 存储在固定 per-type tables，普通配置型 Entity 存储在普通 per-type tables，输出型存储在数据库输出表，瞬态型存储在内存。

#### Scenario: 创建普通配置型 Entity

- **WHEN** 用户创建一个普通 `type: stock` 的 Entity
- **THEN** 系统将其持久化到 `entity_stock` 表
- **AND** 未物化字段 SHALL 写入 `attributes_json`

#### Scenario: 创建输出型 Entity

- **WHEN** Node 执行产出一个 `type: analysis` 的 Entity
- **THEN** 系统将其存储到数据库 `node_outputs` 表

#### Scenario: 实体类型验证

- **WHEN** 实体的 `type` 对应的类型定义设置 `validate: true`
- **THEN** 系统验证 `attributes` 是否符合 schema，不符合时报错
