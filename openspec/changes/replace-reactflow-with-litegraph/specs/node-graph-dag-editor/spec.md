## MODIFIED Requirements

### Requirement: Interactive graph editing
系统 SHALL 支持用户在画布上通过 LiteGraph 原生交互编辑 DAG 数据流。画布 SHALL 实现完整的拖放、连线、删除和框选交互。

#### Scenario: Add node from palette via drop
- **WHEN** 用户从 palette 拖拽一个 Node 到画布并释放
- **THEN** 系统 SHALL 监听 canvas `drop` 事件，调用 `LGraph.add()` 在释放坐标处创建节点实例

#### Scenario: Connect node ports
- **WHEN** 用户从上游节点的 output slot 拖拽连线到下游节点的 input slot
- **THEN** 系统 SHALL 通过 LiteGraph 原生连线机制创建连接，触发 `onConnectionChange` 回调

#### Scenario: Delete graph edge
- **WHEN** 用户选中画布上的连线并按 Delete 键
- **THEN** 系统 SHALL 通过 LiteGraph 原生删除机制移除连接

#### Scenario: Drag node on canvas
- **WHEN** 用户在画布上拖动节点
- **THEN** 节点 SHALL 跟随鼠标移动，位置变更仅更新 LGraph 内部状态，不触发后端请求

#### Scenario: Canvas resize follows container
- **WHEN** 浏览器窗口尺寸变化或容器布局改变
- **THEN** 画布分辨率 SHALL 自动匹配容器实际像素尺寸，交互坐标保持准确

### Requirement: Graph DAG save
系统 MUST 将 LGraph 状态通过 adapter 保存回后端 DAG 配置。

#### Scenario: Save valid graph DAG with position metadata
- **WHEN** 用户手动保存合法 DAG
- **THEN** 系统 SHALL 调用 adapter `toDag()` 导出节点列表、边列表和位置元数据，通过 API 写回后端

#### Scenario: Reject invalid graph DAG
- **WHEN** 用户保存包含环、未知节点或 I/O 类型不匹配的 DAG
- **THEN** 系统 MUST 拒绝保存、返回可读错误并保持原 DAG 文件内容不变

### Requirement: Node Inspector configuration
系统 SHALL 在 Node Graph Inspector 中根据节点类型展示差异化的可配置字段。节点选中通过 LiteGraph `onNodeSelected` 回调桥接到 zustand store。

#### Scenario: Inspect node configuration by type
- **WHEN** 用户在画布中点击选中节点
- **THEN** 系统 SHALL 通过 `onNodeSelected` 回调更新 zustand `selectedNodeId`，Inspector 根据 `node.type` 展示对应编辑字段

#### Scenario: Deselect node clears Inspector
- **WHEN** 用户点击画布空白区域取消选中
- **THEN** 系统 SHALL 通过 `onNodeDeselected` 回调清空 zustand `selectedNodeId`，Inspector 清空显示

#### Scenario: Save node configuration
- **WHEN** 用户在 Inspector 中保存合法节点配置
- **THEN** 系统 SHALL 写回对应 `config/nodes/*.yaml`，并让新配置仅影响后续运行

#### Scenario: Reject invalid node configuration
- **WHEN** 用户在 Inspector 中保存非法节点配置
- **THEN** 系统 MUST 拒绝保存、返回可读错误并保持原 Node 文件内容不变

### Requirement: Graph runtime status overlay
系统 SHALL 在 LiteGraph 画布中通过节点颜色/动画展示运行状态。

#### Scenario: Show node run status
- **WHEN** 运行状态数据更新
- **THEN** 系统 SHALL 通过修改 LGraphNode 的 `bgcolor` 或 `color` 属性展示 `running`（蓝色脉冲）、`succeeded`（绿色）、`failed`（红色）状态

#### Scenario: Show node failure details
- **WHEN** 某节点最近运行失败
- **THEN** 系统 SHALL 在 Inspector 中展示该节点的错误信息（当节点被选中时）
