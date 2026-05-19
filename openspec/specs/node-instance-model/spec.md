# node-instance-model Specification

## Purpose
此规约记录变更 node-type-instance-model 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Instance identification
DAG 中的每个节点实例 SHALL 使用 UUID 作为稳定标识，可选 `alias` 字段作为人类可读标签。

#### Scenario: Instance creation with UUID
- **WHEN** 用户将节点类型拖入 DAG 画布
- **THEN** 系统 SHALL 为新实例生成 UUID 作为 `id`，并将其持久化到 DAG YAML

#### Scenario: Alias assignment
- **WHEN** 用户在 Inspector 中为实例设置 alias
- **THEN** 系统 SHALL 保存 alias 到 DAG YAML，alias 变更不影响边的引用关系

### Requirement: Multiple instances of same type
系统 SHALL 允许同一节点类型在 DAG 中创建多个实例。

#### Scenario: Drag same type twice
- **WHEN** 用户将 `rss-fetcher` 类型拖入画布两次
- **THEN** 系统 SHALL 创建两个独立实例（不同 UUID），各自可独立配置

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

### Requirement: LLM instance skill freedom
LLM 节点实例 SHALL 可以自由配置 skills：取消类型默认的 skill，或追加全局注册表中的任意 skill。

#### Scenario: Disable default skill
- **WHEN** LLM 节点类型默认启用 `[summarize, classify-sentiment]`，用户在实例中取消 `classify-sentiment`
- **THEN** 系统 SHALL 保存实例 skills 为 `[summarize]`

#### Scenario: Add skill beyond type defaults
- **WHEN** 用户为 LLM 实例追加类型未定义的 skill `translate`
- **THEN** 系统 SHALL 接受并保存，实例 skills 包含 `translate`

### Requirement: DAG YAML instance format

DAG YAML SHALL 使用实例对象列表格式存储节点，`config` 字段包含实例级覆盖（包括 `entities` 和 `entity_permissions`）。

#### Scenario: DAG YAML structure with entities

- **WHEN** 系统保存包含实体配置的 DAG
- **THEN** 系统 SHALL 将每个节点序列化为包含 `id`（UUID）、`type`（类型名引用）、`alias`（可选）、`config`（包含 `entities` 和 `entity_permissions`）的对象

#### Scenario: Edge references use instance ID

- **WHEN** 系统保存 DAG 边配置
- **THEN** 系统 SHALL 使用实例 UUID 作为 `from` 和 `to` 的值

