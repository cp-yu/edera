---
capabilities:
  - cap.web.node-instance-model
---
# node-instance-model Specification

## Purpose
定义 Instance identification、Multiple instances of same type、Instance-level configuration、LLM instance skill freedom等能力。
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

### Requirement: Session_dir 字段
`DagNodeInstance.config` SHALL 支持 `session_dir` 字段（可选字符串），控制 LLM 节点的 session 存储位置。

#### Scenario: 添加 session_dir 配置
- **WHEN** 用户在 Inspector 中为 LLM 节点实例设置 `session_dir: "session:llm-analyze:latest"`
- **THEN** 系统 SHALL 保存到 DAG YAML 的实例 `config` 中

#### Scenario: Session_dir 校验
- **WHEN** 用户设置 `session_dir` 为非法格式（如包含非法字符）
- **THEN** 系统 SHALL 拒绝保存并提示格式错误

### Requirement: Tools 字段
`DagNodeInstance.config` SHALL 支持 `tools` 字段（可选字符串数组），覆盖类型层的默认 tools 配置。

#### Scenario: 添加 tools 配置
- **WHEN** 用户在 Inspector 中为 LLM 节点实例设置 `tools: [bash, read, edit, write]`
- **THEN** 系统 SHALL 保存到 DAG YAML 的实例 `config` 中

#### Scenario: Tools 白名单校验
- **WHEN** 用户设置 `tools` 包含非法工具名（不在 pi 支持的工具列表中）
- **THEN** 系统 SHALL 拒绝保存并提示非法工具名

### Requirement: Model 字段移至实例层
`model` 字段 SHALL 从 `NodeConfig`（类型层）移至 `DagNodeInstance.config`（实例层）。

#### Scenario: 实例层 model 配置
- **WHEN** 用户在 Inspector 中为 LLM 节点实例设置 `model: "hf-share/deepseek-v4-flash"`
- **THEN** 系统 SHALL 保存到 DAG YAML 的实例 `config` 中

#### Scenario: 类型层不再包含 model
- **WHEN** 系统加载 `NodeConfig` 定义
- **THEN** 系统 SHALL 不期望 `model` 字段存在于类型层配置中

#### Scenario: 实例未设置 model
- **WHEN** 实例 `config` 中未设置 `model` 字段
- **THEN** executor SHALL 返回错误 "model not configured for instance"

### Requirement: 类型层 tools 默认值
`NodeConfig` SHALL 支持 `tools` 字段（可选字符串数组），作为该类型所有实例的默认工具集。

#### Scenario: 类型层定义默认 tools
- **WHEN** `NodeConfig` 定义 `tools: [bash]`
- **THEN** 该类型的所有实例默认继承 `tools: [bash]`，除非实例层覆盖

#### Scenario: 类型层未定义 tools
- **WHEN** `NodeConfig` 未定义 `tools` 字段
- **THEN** 实例默认 `tools: []`（无工具，等同 `--no-tools`）

### Requirement: Sub-DAG instance fields
DAG YAML 实例对象 SHALL 支持 sub-DAG 节点所需的 `dag_ref` 和 `input_mapping` 字段。多个实例 MAY 引用同一个 `dag_ref`，但每个实例仍 MUST 使用独立 `id`。

#### Scenario: Save sub-DAG instance fields
- **WHEN** 系统保存 sub-DAG 节点实例
- **THEN** DAG YAML SHALL 将该实例序列化为包含 `id`、`type: "dag"`、`dag_ref`、`input_mapping`、`alias` 和 `config` 的对象

#### Scenario: Multiple sub-DAG instances share target
- **WHEN** 用户在同一 DAG 中创建两个引用 `common-subdag` 的 sub-DAG 节点实例
- **THEN** 系统 SHALL 为两个实例保存不同的 `id`
- **AND** 两个实例 MAY 保存相同的 `dag_ref`

#### Scenario: Preserve sub-DAG instance fields in draft save
- **WHEN** Workbench 自动保存包含 sub-DAG 节点实例的 DAG 草稿
- **THEN** 保存 payload SHALL 保留该实例的 `dag_ref` 与 `input_mapping`

