## MODIFIED Requirements

### Requirement: Node palette with drag-to-add
系统 SHALL 在左侧面板展示可用节点列表，支持拖拽到画布添加节点引用。画布 SHALL 实现 `onDragOver` 和 `onDrop` 事件处理，将拖拽的节点原型转化为 DAG 节点实例。

#### Scenario: Drag node to canvas
- **WHEN** 用户从 Palette 拖拽一个节点到画布
- **THEN** 系统 SHALL 在鼠标释放的画布坐标处创建该节点实例，并添加到当前 DAG 拓扑中

#### Scenario: Drop position accuracy
- **WHEN** 用户在画布任意位置释放拖拽的节点
- **THEN** 系统 SHALL 使用 `screenToFlowPosition` 将屏幕坐标转换为画布坐标，节点出现在鼠标释放位置

#### Scenario: Group nodes by type
- **WHEN** Palette 加载节点列表
- **THEN** 系统 SHALL 按节点类型分组展示（LLM 节点、功能节点等）

### Requirement: Custom node rendering with target colors
系统 SHALL 使用自定义 React Flow 节点组件，提供四边 Handle（上下左右各一对 source/target），默认隐藏，hover 时显示。

#### Scenario: Four-side handles on hover
- **WHEN** 用户将鼠标悬停在节点上
- **THEN** 系统 SHALL 显示节点四边的 8 个 Handle（上下左右各一个 source 和一个 target）

#### Scenario: Handles hidden by default
- **WHEN** 节点未被 hover
- **THEN** 系统 SHALL 隐藏所有 Handle（opacity: 0）

#### Scenario: Single target node color
- **WHEN** 节点仅关联一个 target
- **THEN** 系统 SHALL 使用该 target 的预定义颜色作为节点左边框色

#### Scenario: Multi-target node color
- **WHEN** 节点关联多个 target
- **THEN** 系统 SHALL 使用各 target 颜色的 RGB 均值作为节点左边框色

### Requirement: Edge arrows and visual feedback
系统 SHALL 在所有连接线末端显示箭头标记，表示数据流方向。

#### Scenario: Edge arrow marker
- **WHEN** 画布渲染连接线
- **THEN** 系统 SHALL 在 edge 的 target 端显示闭合箭头（MarkerType.ArrowClosed）

#### Scenario: Running animation
- **WHEN** DAG 正在运行
- **THEN** 系统 SHALL 对所有 edge 启用动画效果（animated: true）

### Requirement: Interactive edge management
系统 SHALL 支持用户在画布上通过 Handle 交互新增连线，以及选中连线后删除。

#### Scenario: Connect nodes via handle drag
- **WHEN** 用户从一个节点的 source Handle 拖拽连线到另一个节点的 target Handle
- **THEN** 系统 SHALL 创建新的 edge 并添加到画布，记录 sourceHandle 和 targetHandle 标识

#### Scenario: Delete edge with keyboard
- **WHEN** 用户选中一条 edge 并按下 Delete 键
- **THEN** 系统 SHALL 从画布中移除该 edge

### Requirement: Node position persistence
系统 SHALL 持久化用户手动拖拽的节点位置，不因选中/取消选中操作而重置。

#### Scenario: Drag node preserves position
- **WHEN** 用户拖拽节点到新位置后点击画布空白区域
- **THEN** 系统 SHALL 保持节点在拖拽后的位置，不回归初始位置

#### Scenario: Position saved to backend
- **WHEN** 用户保存 DAG
- **THEN** 系统 SHALL 将所有节点的当前位置写入 `ui.nodes` 元数据

### Requirement: Auto-layout tool
系统 SHALL 提供自动布局工具按钮，使用 dagre 算法计算层级布局。

#### Scenario: Trigger auto-layout
- **WHEN** 用户点击自动布局按钮
- **THEN** 系统 SHALL 使用 dagre 算法重新计算所有节点位置并更新画布

#### Scenario: Layout direction
- **WHEN** 自动布局执行
- **THEN** 系统 SHALL 默认使用 TB（top-bottom）方向排布

### Requirement: Node inspector with editable/readonly fields
系统 SHALL 在右侧 Inspector 面板根据节点类型展示差异化的编辑字段。

#### Scenario: Fetcher node inspector
- **WHEN** 用户选中类型为 `fetcher` 的节点
- **THEN** 系统 SHALL 展示 source_names、timeout_seconds、parameters 编辑字段

#### Scenario: LLM node inspector
- **WHEN** 用户选中类型为 `llm` 的节点
- **THEN** 系统 SHALL 展示 model、timeout_seconds、skills、parameters 编辑字段

#### Scenario: Aggregator node inspector
- **WHEN** 用户选中类型为 `aggregator` 的节点
- **THEN** 系统 SHALL 展示 timeout_seconds、parameters 编辑字段

#### Scenario: Common readonly fields
- **WHEN** Inspector 展示任意类型节点
- **THEN** 系统 SHALL 以只读方式展示 name、type、input_type、output_type 字段
