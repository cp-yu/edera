## ADDED Requirements

### Requirement: DAG persistence format
系统 SHALL 使用实例对象列表格式持久化 DAG 配置，每个节点为包含 UUID id、类型引用和实例配置的对象。

#### Scenario: Save DAG with instance format
- **WHEN** 系统保存 DAG 配置到 YAML
- **THEN** 系统 SHALL 将 `nodes` 序列化为对象列表，每个对象包含 `id`（UUID）、`type`（节点类型名）、`alias`（可选）、`config`（实例级覆盖参数）

#### Scenario: Edge references use instance UUID
- **WHEN** 系统保存 DAG 边配置
- **THEN** 系统 SHALL 使用实例 UUID 作为 `from` 和 `to` 字段的值

#### Scenario: Load DAG with instance format
- **WHEN** 系统加载 DAG YAML 文件
- **THEN** 系统 SHALL 解析每个节点对象，通过 `type` 字段关联节点类型定义，通过 `config` 字段覆盖运行时参数

### Requirement: Handle rendering driven by role
系统 SHALL 根据节点类型的 `role` 决定 Handle 的渲染：source 节点不渲染输入 Handle，sink 节点不渲染输出 Handle。

#### Scenario: Source node has no input handle
- **WHEN** 画布渲染一个 `role: source` 的节点实例
- **THEN** 系统 SHALL 仅渲染右侧输出 Handle，不渲染左侧输入 Handle

#### Scenario: Sink node has no output handle
- **WHEN** 画布渲染一个 `role: sink` 的节点实例
- **THEN** 系统 SHALL 仅渲染左侧输入 Handle，不渲染右侧输出 Handle

#### Scenario: Processor node has both handles
- **WHEN** 画布渲染一个 `role: processor` 的节点实例
- **THEN** 系统 SHALL 同时渲染左侧输入 Handle 和右侧输出 Handle

### Requirement: Instance-aware Inspector
系统 SHALL 在选中节点实例时展示实例级配置表单，根据节点类型（LLM/Function）展示不同的可编辑字段。

#### Scenario: LLM instance Inspector
- **WHEN** 用户选中一个 LLM 节点实例
- **THEN** 系统 SHALL 展示可编辑字段：alias、skills（多选，可增删）、model（下拉）、parameters（schema 驱动表单）

#### Scenario: Function instance Inspector
- **WHEN** 用户选中一个 Function 节点实例
- **THEN** 系统 SHALL 展示可编辑字段：alias、source_names（仅 source 类型）、parameters（schema 驱动表单）

#### Scenario: Read-only type info display
- **WHEN** 用户选中任意节点实例
- **THEN** 系统 SHALL 以只读方式展示类型信息：type name、role、input_type、output_type
