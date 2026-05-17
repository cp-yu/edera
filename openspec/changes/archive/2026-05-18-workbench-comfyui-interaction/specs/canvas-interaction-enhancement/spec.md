## ADDED Requirements

### Requirement: Bezier curve edge rendering
系统 SHALL 使用贝塞尔曲线渲染所有连线，提供视觉容错能力，避免直线交叉时的混乱。

#### Scenario: Default edge type
- **WHEN** 画布渲染连线
- **THEN** 系统 SHALL 使用 `bezier` 类型渲染 edge，曲率根据 source/target 距离自适应

#### Scenario: Edge color differentiation
- **WHEN** 画布渲染连线
- **THEN** 系统 SHALL 根据 source 节点类型为连线着色，使数据流来源可视化区分

### Requirement: Context menu for edges and nodes
系统 SHALL 提供右键上下文菜单，支持对节点和连线的快捷操作。

#### Scenario: Edge context menu
- **WHEN** 用户右键点击一条 edge
- **THEN** 系统 SHALL 显示上下文菜单，包含"反转方向"和"删除"操作

#### Scenario: Reverse edge direction
- **WHEN** 用户在 edge 上下文菜单中选择"反转方向"
- **THEN** 系统 SHALL 删除原 edge 并创建 source/target 互换的新 edge，保留 handle 位置映射

#### Scenario: Node context menu
- **WHEN** 用户右键点击一个节点
- **THEN** 系统 SHALL 显示上下文菜单，包含"删除节点"和"断开所有连线"操作

### Requirement: Snap to grid
系统 SHALL 支持节点拖拽时吸附到网格，保证布局整齐。

#### Scenario: Grid snapping enabled
- **WHEN** 用户拖拽节点
- **THEN** 系统 SHALL 将节点位置吸附到 20px 网格

#### Scenario: Grid visual
- **WHEN** 画布渲染背景
- **THEN** 系统 SHALL 显示与 snap 网格对齐的点阵背景

### Requirement: Alignment guidelines
系统 SHALL 在节点拖拽时显示对齐辅助线，帮助用户对齐相邻节点。

#### Scenario: Horizontal alignment guide
- **WHEN** 用户拖拽节点且其中心 Y 坐标与另一节点中心 Y 坐标差值 < 5px
- **THEN** 系统 SHALL 显示水平对齐辅助线

#### Scenario: Vertical alignment guide
- **WHEN** 用户拖拽节点且其中心 X 坐标与另一节点中心 X 坐标差值 < 5px
- **THEN** 系统 SHALL 显示垂直对齐辅助线

#### Scenario: Guide disappears on drop
- **WHEN** 用户释放节点
- **THEN** 系统 SHALL 隐藏所有对齐辅助线

### Requirement: Undo and Redo
系统 SHALL 支持画布操作的撤销和重做，基于 state snapshot 栈。

#### Scenario: Undo last action
- **WHEN** 用户按下 Ctrl+Z
- **THEN** 系统 SHALL 恢复画布到上一个 snapshot 状态（节点位置 + 连线）

#### Scenario: Redo undone action
- **WHEN** 用户按下 Ctrl+Shift+Z
- **THEN** 系统 SHALL 重新应用最近一次被撤销的 snapshot

#### Scenario: Snapshot stack limit
- **WHEN** snapshot 栈超过 50 条
- **THEN** 系统 SHALL 丢弃最早的 snapshot，保持栈深度 <= 50

#### Scenario: New action clears redo stack
- **WHEN** 用户在 undo 后执行新操作
- **THEN** 系统 SHALL 清空 redo 栈
