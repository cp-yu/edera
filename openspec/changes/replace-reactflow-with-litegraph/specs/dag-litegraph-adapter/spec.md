## ADDED Requirements

### Requirement: DAG to LGraph conversion
系统 SHALL 提供 `toGraph()` 方法将后端 DAG 格式转换为 LGraph 可消费的节点和连接。

#### Scenario: Convert DAG nodes to LGraph nodes
- **WHEN** 加载 DAG 数据
- **THEN** adapter SHALL 为每个 DAG node 创建对应的 LGraphNode 实例，设置 title、position（从 `ui.nodes` 读取）和 slots

#### Scenario: Convert DAG edges to LGraph connections
- **WHEN** 加载 DAG 数据
- **THEN** adapter SHALL 为每条 DAG edge 创建 LGraph connection，映射 source/target 和对应 slot index

#### Scenario: Handle missing UI metadata
- **WHEN** DAG 数据中 `ui.nodes` 不包含某节点的位置信息
- **THEN** adapter SHALL 为该节点分配默认位置（0,0），不阻断加载

### Requirement: LGraph to DAG conversion
系统 SHALL 提供 `toDag()` 方法将 LGraph 当前状态导出为后端 DAG 格式。

#### Scenario: Export LGraph nodes to DAG format
- **WHEN** 用户触发保存
- **THEN** adapter SHALL 从 LGraph 导出所有节点的 name、position，写入 DAG 的 `nodes` 列表和 `ui.nodes` 元数据

#### Scenario: Export LGraph connections to DAG edges
- **WHEN** 用户触发保存
- **THEN** adapter SHALL 从 LGraph 导出所有连接，转换为 DAG 的 `edges` 格式（含 source、target、sourceHandle、targetHandle）

### Requirement: Draft persistence
系统 SHALL 提供自动草稿持久化机制，将 LGraph 状态定期保存到 localStorage。

#### Scenario: Auto-save draft at interval
- **WHEN** 画布处于编辑状态且自动草稿已启用
- **THEN** 系统 SHALL 每隔配置间隔（默认 60s）将 LGraph 序列化结果存入 `localStorage['dag-draft:${dagName}']`

#### Scenario: Restore draft on load
- **WHEN** 用户打开 DAG 且 localStorage 中存在对应草稿
- **THEN** 系统 SHALL 提示用户是否恢复草稿，确认后从草稿恢复 LGraph 状态

#### Scenario: Clear draft on save
- **WHEN** 用户手动保存成功
- **THEN** 系统 SHALL 清除对应 dagName 的 localStorage 草稿

#### Scenario: Draft interval configurable
- **WHEN** 用户修改草稿间隔设置
- **THEN** 系统 SHALL 按新间隔执行自动草稿，设置为 0 时禁用自动草稿
