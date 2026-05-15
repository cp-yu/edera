# node-graph-dag-editor Specification

## Purpose
此规约记录变更 add-node-graph-dag-editor 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Node Graph editor entry
系统 SHALL 在 Web 控制台提供 Node Graph DAG 编辑入口，并将其作为 DAG 可视化编辑的主入口。

#### Scenario: Open Node Graph editor
- **WHEN** 用户打开 DAG 编辑入口
- **THEN** 系统 SHALL 展示包含节点 palette、画布和 Inspector 区域的 Node Graph 页面

#### Scenario: Preserve fallback editors
- **WHEN** 用户需要直接排查配置
- **THEN** 系统 SHALL 保留 raw YAML 或结构化表格编辑入口作为兜底

### Requirement: Graph schema API
系统 SHALL 提供图编辑所需的节点原型和 DAG 图状态 JSON API，避免前端直接解析 YAML。

#### Scenario: Load node prototypes
- **WHEN** Node Graph 编辑器加载
- **THEN** 系统 SHALL 返回可用 Node 原型，包括 `name`、`type`、`input_type`、`output_type`、`skills`、`model`、`source_names`、`timeout_seconds` 和 `parameters`

#### Scenario: Load DAG graph state
- **WHEN** Node Graph 编辑器打开指定 DAG
- **THEN** 系统 SHALL 返回该 DAG 的节点实例、边、fan flags 和 UI 布局元数据

### Requirement: Interactive graph editing
系统 SHALL 支持用户在画布上通过节点和端口交互编辑 DAG 数据流。

#### Scenario: Add node from palette
- **WHEN** 用户从 palette 添加一个 Node 到画布
- **THEN** 系统 SHALL 在 DAG 草稿中加入该 Node，并在画布上显示其输入/输出端口

#### Scenario: Connect node ports
- **WHEN** 用户从上游输出端口连接到下游输入端口
- **THEN** 系统 SHALL 在 DAG 草稿中创建对应边，并在画布上显示数据流连线

#### Scenario: Delete graph edge
- **WHEN** 用户删除画布上的连线
- **THEN** 系统 SHALL 从 DAG 草稿中移除对应边

### Requirement: Graph DAG save
系统 MUST 将 Node Graph 草稿保存回现有 DAG 执行语义，并复用后端 DAG 校验。

#### Scenario: Save valid graph DAG
- **WHEN** 用户保存合法 Node Graph DAG
- **THEN** 系统 SHALL 写回对应 `config/dags/*.yaml` 并保留节点 UI 布局元数据

#### Scenario: Reject invalid graph DAG
- **WHEN** 用户保存包含环、未知节点或 I/O 类型不匹配的 Node Graph DAG
- **THEN** 系统 MUST 拒绝保存、返回可读错误并保持原 DAG 文件内容不变

### Requirement: Node Inspector configuration
系统 SHALL 在 Node Graph Inspector 中展示并编辑选中节点的可配置字段。

#### Scenario: Inspect node configuration
- **WHEN** 用户选中画布中的节点
- **THEN** 系统 SHALL 在 Inspector 展示该节点的 `skills[]`、`model`、`source_names`、`timeout_seconds` 和 `parameters`

#### Scenario: Save node configuration
- **WHEN** 用户在 Inspector 中保存合法节点配置
- **THEN** 系统 SHALL 写回对应 `config/nodes/*.yaml`，并让新配置仅影响后续运行

#### Scenario: Reject invalid node configuration
- **WHEN** 用户在 Inspector 中保存非法节点配置
- **THEN** 系统 MUST 拒绝保存、返回可读错误并保持原 Node 文件内容不变

### Requirement: Graph runtime status overlay
系统 SHALL 在 Node Graph 中展示最近或当前运行的节点状态。

#### Scenario: Show node run status
- **WHEN** Node Graph 编辑器加载运行状态
- **THEN** 系统 SHALL 在对应节点上展示 `pending`、`running`、`succeeded`、`failed` 或 `unknown` 状态

#### Scenario: Show node failure details
- **WHEN** 某节点最近运行失败
- **THEN** 系统 SHALL 在节点或 Inspector 中展示该节点的错误信息

