## MODIFIED Requirements

### Requirement: Interactive graph editing
系统 SHALL 支持用户在画布上通过节点和端口交互编辑 DAG 数据流。画布 SHALL 实现完整的拖放（drop）、连线（connect）和删除（delete）交互。

#### Scenario: Add node from palette via drop
- **WHEN** 用户从 palette 拖拽一个 Node 到画布并释放
- **THEN** 系统 SHALL 调用 `onDrop` 处理器，在释放坐标处创建节点实例并加入 DAG 草稿

#### Scenario: Connect node ports
- **WHEN** 用户从上游节点的 source Handle 拖拽连线到下游节点的 target Handle
- **THEN** 系统 SHALL 通过 `onConnect` 回调在 DAG 草稿中创建对应边，edge 记录 `sourceHandle` 和 `targetHandle` 标识

#### Scenario: Delete graph edge
- **WHEN** 用户选中画布上的连线并按 Delete 键
- **THEN** 系统 SHALL 通过 `onEdgesDelete` 从 DAG 草稿中移除对应边

#### Scenario: Drag node on canvas
- **WHEN** 用户在画布上拖动节点
- **THEN** 节点 SHALL 跟随鼠标移动，位置变更仅更新本地状态，不触发从服务端重建

#### Scenario: Canvas resize follows container
- **WHEN** 浏览器窗口尺寸变化或容器布局改变
- **THEN** 画布分辨率 SHALL 自动匹配容器实际像素尺寸，交互坐标保持准确

### Requirement: Graph DAG save
系统 MUST 将 Node Graph 草稿保存回现有 DAG 执行语义，包含 Handle 元数据。

#### Scenario: Save valid graph DAG with handle metadata
- **WHEN** 用户保存合法 Node Graph DAG
- **THEN** 系统 SHALL 写回对应 DAG 配置，`ui.nodes` 保存节点位置，`ui.edges` 保存 edge 的 sourceHandle/targetHandle 信息

#### Scenario: Reject invalid graph DAG
- **WHEN** 用户保存包含环、未知节点或 I/O 类型不匹配的 Node Graph DAG
- **THEN** 系统 MUST 拒绝保存、返回可读错误并保持原 DAG 文件内容不变

### Requirement: Node Inspector configuration
系统 SHALL 在 Node Graph Inspector 中根据节点类型展示差异化的可配置字段。

#### Scenario: Inspect node configuration by type
- **WHEN** 用户选中画布中的节点
- **THEN** 系统 SHALL 根据 `node.type` 在 Inspector 展示对应的编辑字段集合

#### Scenario: Deselect node clears Inspector
- **WHEN** 用户点击画布空白区域取消选中
- **THEN** Inspector SHALL 清空节点配置显示
