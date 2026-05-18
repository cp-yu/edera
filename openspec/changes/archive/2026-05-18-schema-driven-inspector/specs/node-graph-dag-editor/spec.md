## MODIFIED Requirements

### Requirement: Instance-aware Inspector
系统 SHALL 在选中节点实例时展示 schema 驱动的配置表单，根据后端返回的 `inspector_schema` 动态渲染编辑字段。

#### Scenario: Schema-driven form rendering
- **WHEN** 用户选中画布中的节点实例
- **THEN** 系统 SHALL 读取该实例的 `inspector_schema`，为每个 schema property 渲染对应 UI 控件：`string` 渲染文本输入、`string + enum` 渲染下拉选择、`integer/number` 渲染数字输入、`boolean` 渲染开关

#### Scenario: LLM instance Inspector
- **WHEN** 用户选中一个 LLM 节点实例
- **THEN** 系统 SHALL 展示可编辑字段：`alias`（独立文本输入）、`model`（下拉选择）、`skills`（多选标签）、`timeout_seconds`（数字输入），以及 `parameters_schema` 定义的自定义字段

#### Scenario: Function instance Inspector
- **WHEN** 用户选中一个 Function 节点实例
- **THEN** 系统 SHALL 展示可编辑字段：`alias`（独立文本输入）、`source_names`（多选标签，仅 source role）、`timeout_seconds`（数字输入），以及 `parameters_schema` 定义的自定义字段

#### Scenario: Read-only type info display
- **WHEN** 用户选中任意节点实例
- **THEN** 系统 SHALL 以只读方式展示类型信息：`type_name`、`role`、`input_type`、`output_type`

#### Scenario: Value display priority
- **WHEN** schema 驱动表单渲染字段值
- **THEN** 系统 SHALL 优先显示实例 `config` 中的值；若无，显示类型默认值；placeholder SHALL 显示类型默认值以提示回退目标

#### Scenario: Clear field reverts to type default
- **WHEN** 用户清空某个 schema 字段的值并保存
- **THEN** 系统 SHALL 从实例 `config` 中删除该字段，运行时回退到类型默认值

#### Scenario: Diff-only save
- **WHEN** 用户保存实例配置
- **THEN** 系统 SHALL 仅将与类型默认值不同的字段写入实例 `config`，不存储与默认值相同的冗余数据

#### Scenario: Unsupported schema type fallback
- **WHEN** `inspector_schema` 中某字段的类型不在支持列表（`string`、`integer`、`number`、`boolean`）中
- **THEN** 系统 SHALL 将该字段渲染为 raw JSON 文本输入

#### Scenario: Deselect node clears Inspector
- **WHEN** 用户点击画布空白区域取消选中
- **THEN** Inspector SHALL 清空节点配置显示

### Requirement: Node Inspector configuration
系统 SHALL 在 Node Graph Inspector 中根据 `inspector_schema` 展示 schema 驱动的可配置字段。

#### Scenario: Inspect node configuration by schema
- **WHEN** 用户选中画布中的节点
- **THEN** 系统 SHALL 根据 `inspector_schema` 在 Inspector 展示对应的编辑控件集合，不再使用硬编码的节点类型条件逻辑

#### Scenario: Save node configuration
- **WHEN** 用户在 Inspector 中保存合法节点配置
- **THEN** 系统 SHALL 将 schema 字段拆分回实例 `config`（顶层字段如 `model`/`skills` 保留在 config 顶层，`param.*` 前缀字段写入 `config.parameters`），并通过 `PUT /api/graph/dag/{name}` 持久化

#### Scenario: Reject invalid node configuration
- **WHEN** 用户在 Inspector 中保存非法节点配置
- **THEN** 系统 MUST 拒绝保存、返回可读错误并保持原 DAG 配置不变
