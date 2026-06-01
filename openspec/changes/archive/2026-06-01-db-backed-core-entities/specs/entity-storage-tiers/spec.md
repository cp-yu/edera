## MODIFIED Requirements

### Requirement: 三层存储模型

系统 SHALL 支持 Entity 按生命周期分层存储：核心配置型 Entity 使用数据库 per-type tables，输出型 Entity 使用数据库输出表，瞬态型 Entity 使用内存。Entity Store MUST 对上层提供统一查询接口，屏蔽存储层差异。YAML 文件 MAY 作为 import/export/template 格式存在，但 MUST NOT 作为核心配置型 Entity 的运行时 source of truth。

#### Scenario: 核心配置型 Entity 存储在数据库 per-type table

- **WHEN** 用户创建一个 `type: node` 的 Entity
- **THEN** 系统将其持久化到 `entity_node` 表
- **AND** 系统 MUST NOT 将其作为运行时配置写入 `config/nodes/`

#### Scenario: 输出型 Entity 存储在数据库

- **WHEN** Node 执行产出一个 `type: analysis` 的 Entity
- **THEN** 系统将其存储到数据库 `node_outputs` 表，payload 为 JSON 格式

#### Scenario: 瞬态 Entity 存储在内存

- **WHEN** DAG run 开始时创建 run metadata Entity
- **THEN** 系统将其保存在内存中，run 结束后释放

#### Scenario: 统一查询跨存储层

- **WHEN** 用户查询 `entity:analysis:00700-2026-05-21`
- **THEN** Entity Store 自动路由到数据库层查询并返回结果，调用方无需感知存储层

### Requirement: 存储层路由规则

系统 SHALL 根据 EntityType 的配置决定 Entity 存储在哪一层。EntityType schema MUST 声明 `storage_tier` 字段。对于 `node`、`dag`、`trigger`、`resource`，`storage_tier: database` MUST 路由到对应固定 per-type table，而不是 `node_outputs`。

#### Scenario: EntityType 声明核心数据库存储

- **WHEN** EntityType `node` 的 schema 中 `storage_tier: database`
- **THEN** 所有 `type: node` 的 Entity 存储在 `entity_node` 表

#### Scenario: EntityType 声明输出数据库存储

- **WHEN** EntityType `analysis` 的 schema 中 `storage_tier: database`
- **THEN** 所有 `type: analysis` 的输出型 Entity 存储在 `node_outputs` 表

#### Scenario: EntityType 声明内存存储

- **WHEN** EntityType `run-metadata` 的 schema 中 `storage_tier: memory`
- **THEN** 所有 `type: run-metadata` 的 Entity 仅存在于内存
