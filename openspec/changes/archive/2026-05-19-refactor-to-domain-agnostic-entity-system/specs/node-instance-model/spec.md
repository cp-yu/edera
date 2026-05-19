## MODIFIED Requirements

### Requirement: Instance-level configuration

节点实例 SHALL 仅能覆盖运行时参数，结构性字段由类型定义锁定。实例配置新增 `entities` 和 `entity_permissions` 字段。

#### Scenario: LLM instance configurable fields

- **WHEN** 用户编辑 LLM 节点实例配置
- **THEN** 系统 SHALL 允许修改：`alias`、`skills`（自由增删）、`model`、`parameters`、`entities`、`entity_permissions`

#### Scenario: Function instance configurable fields

- **WHEN** 用户编辑 Function 节点实例配置
- **THEN** 系统 SHALL 允许修改：`alias`、`source_names`、`parameters`、`entities`、`entity_permissions`

#### Scenario: Structural fields locked

- **WHEN** 用户尝试修改实例的 `input_type`、`output_type`、`role`、`handler` 或 `system_prompt_file`
- **THEN** 系统 SHALL 拒绝修改（这些字段由类型定义决定）

#### Scenario: Entity configuration

- **WHEN** 用户在实例配置中设置 `entities: ["stock:00700.HK", "rss-source:sample-rss"]`
- **THEN** 系统 SHALL 保存到实例的 `config` 中，节点执行时可访问这些实体

#### Scenario: Entity permission overrides

- **WHEN** 用户在实例配置中设置 `entity_permissions: {stock: {code: read-write}}`
- **THEN** 系统 SHALL 验证是否为合法提权，保存到实例的 `config` 中

### Requirement: DAG YAML instance format

DAG YAML SHALL 使用实例对象列表格式存储节点，`config` 字段包含实例级覆盖（包括 `entities` 和 `entity_permissions`）。

#### Scenario: DAG YAML structure with entities

- **WHEN** 系统保存包含实体配置的 DAG
- **THEN** 系统 SHALL 将每个节点序列化为包含 `id`（UUID）、`type`（类型名引用）、`alias`（可选）、`config`（包含 `entities` 和 `entity_permissions`）的对象

#### Scenario: Edge references use instance ID

- **WHEN** 系统保存 DAG 边配置
- **THEN** 系统 SHALL 使用实例 UUID 作为 `from` 和 `to` 的值
