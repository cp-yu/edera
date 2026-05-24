## MODIFIED Requirements

### Requirement: EntityType schema 字段即能力声明

系统 SHALL 通过 EntityType schema 中特定字段的存在来声明 Entity 的能力。EntityType 注册来源扩展为双层：扩展 manifest 声明 + 用户配置覆盖。用户配置优先级 MUST 高于扩展声明。

#### Scenario: 可执行能力声明

- **WHEN** 一个 EntityType schema 定义中包含 `handler` 字段
- **THEN** 系统识别该类型的 Entity 为可执行的（Node）

#### Scenario: DAG 能力声明

- **WHEN** 一个 EntityType schema 定义中包含 `edges` 和 `nodes` 字段
- **THEN** 系统识别该类型的 Entity 为 DAG

#### Scenario: Trigger 能力声明

- **WHEN** 一个 EntityType schema 定义中包含 `wait_for` 和 `target` 字段
- **THEN** 系统识别该类型的 Entity 为 Trigger

#### Scenario: 扩展注册 entity type

- **WHEN** 扩展 manifest 声明 `entity_types: [{name: rss-source, display_name: "RSS 源", ...}]`
- **THEN** 核心 SHALL 将该 entity type 注册到全局 entity type registry

#### Scenario: 用户配置覆盖扩展 entity type

- **WHEN** 扩展声明 `rss-source` entity type 的 `display_template` 为 `"{name}"`，用户 config 中定义为 `"{name} ({url})"`
- **THEN** 系统 SHALL 使用用户配置的 `display_template`，扩展声明的其他未覆盖字段保持不变

#### Scenario: 纯用户自定义 entity type

- **WHEN** 用户在 `config/schemas/` 中定义了 `custom-source` entity type，无任何扩展声明该类型
- **THEN** 系统 SHALL 正常注册该 entity type，行为与扩展声明的类型一致
