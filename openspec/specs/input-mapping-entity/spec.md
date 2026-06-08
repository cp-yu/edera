# input-mapping-entity Specification

## Purpose
此规约记录变更 runtime-input-override 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: InputMapping EntityType 定义

系统 SHALL 定义核心 EntityType `input_mapping`，包含 `name`、`shared`、`nodes`、`append_nodes` 字段。

#### Scenario: 创建 InputMapping entity

- **WHEN** 创建 entity `{id: "entity://test-mapping", type: "input_mapping", attributes: {name: "test", shared: {param: "output.field"}}}`
- **THEN** 系统成功创建 entity 并存储到 `entity_input_mapping` 表

#### Scenario: InputMapping 包含 shared 映射

- **WHEN** InputMapping entity 的 `shared` 字段为 `{symbol: "output.symbol", date: "output.date"}`
- **THEN** 该映射用于生成子 DAG 的 `sourceSharedInputs`

#### Scenario: InputMapping 包含 nodes 映射

- **WHEN** InputMapping entity 的 `nodes` 字段为 `{special_node: "output.config"}`
- **THEN** 该映射用于生成子 DAG 的 `nodeInputs`

#### Scenario: InputMapping 包含 append_nodes

- **WHEN** InputMapping entity 的 `append_nodes` 字段为 `["node_1", "node_2"]`
- **THEN** 子 DAG 的 `node_1` 和 `node_2` 使用追加模式

### Requirement: InputMapping entity 的系统保护

InputMapping EntityType SHALL 标记为 `system_protected: true`，不允许用户删除类型定义。

#### Scenario: 用户尝试删除 InputMapping EntityType

- **WHEN** 用户调用 DELETE `/api/entity-types/input_mapping`
- **THEN** 系统返回 403 错误

### Requirement: Sub-DAG input_mapping 支持 entity 引用

`DagNodeConfig.input_mapping` SHALL 支持 `dict[str, str]` 或 `str` 类型。当为 `str` 时，系统 SHALL 从 entity store 读取对应的 InputMapping entity。

#### Scenario: 内联 dict 形式

- **WHEN** Sub-DAG 节点的 `input_mapping` 为 `{symbol: "output.symbol"}`
- **THEN** 系统使用该 dict 生成子 DAG 的 `sourceSharedInputs`

#### Scenario: Entity 引用形式

- **WHEN** Sub-DAG 节点的 `input_mapping` 为 `"entity://scoring-mapping"`
- **THEN** 系统从 entity store 读取该 entity，使用其 `shared`、`nodes`、`append_nodes` 字段

#### Scenario: Entity 引用不存在

- **WHEN** Sub-DAG 节点的 `input_mapping` 为 `"entity://non-existent"`
- **THEN** 系统抛出错误 "InputMapping entity not found: entity://non-existent"

### Requirement: InputMapping 解析和应用

系统 SHALL 在执行 Sub-DAG 节点时，根据 `input_mapping` 从父节点输出映射值，生成子 DAG 的 `sourceSharedInputs`、`nodeInputs`、`appendNodes`。

#### Scenario: 映射父节点输出到子 DAG 共享输入

- **WHEN** InputMapping 的 `shared` 为 `{symbol: "output.symbol"}` 且父节点输出为 `{output: {symbol: "AAPL"}}`
- **THEN** 子 DAG 的 `sourceSharedInputs` 为 `{symbol: "AAPL"}`

#### Scenario: 映射父节点输出到子 DAG 节点输入

- **WHEN** InputMapping 的 `nodes` 为 `{special: "output.config"}` 且父节点输出为 `{output: {config: {...}}}`
- **THEN** 子 DAG 的 `nodeInputs` 为 `{special: {...}}`

#### Scenario: 映射路径不存在

- **WHEN** InputMapping 的 `shared` 为 `{param: "output.missing"}` 但父节点输出中不存在 `output.missing`
- **THEN** 该映射项被跳过，不包含在子 DAG 的 `sourceSharedInputs` 中

### Requirement: Web Console 管理 InputMapping entity

Web Console SHALL 支持创建、编辑、查看、删除 InputMapping entity。

#### Scenario: Entity 管理页面列出 InputMapping

- **WHEN** 用户访问 Entity 管理页面并选择类型 `input_mapping`
- **THEN** 页面显示所有 InputMapping entities

#### Scenario: 创建 InputMapping entity

- **WHEN** 用户在 Entity 管理页面创建新 InputMapping，填写 `name`、`shared`、`nodes`、`append_nodes`
- **THEN** 系统创建 entity 并刷新列表

