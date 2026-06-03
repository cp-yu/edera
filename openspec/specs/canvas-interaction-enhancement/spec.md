---
capabilities:
  - cap.web.canvas-interaction-enhancement
---
# canvas-interaction-enhancement Specification

## Purpose

定义 Workbench 画布交互增强能力，覆盖连线视觉、右键菜单、网格吸附、对齐辅助线和撤销重做。
## Requirements
### Requirement: Curved edge rendering
系统 SHALL 使用平滑曲线路径渲染所有连线，并根据 source 节点类型着色。

#### Scenario: Default curved edges
- **WHEN** 画布渲染连线
- **THEN** 系统 SHALL 使用曲线路径渲染 edge，而不是直角折线或纯直线

#### Scenario: Edge color differentiation
- **WHEN** 画布渲染连线
- **THEN** 系统 SHALL 根据 source 节点类型为连线着色，使数据流来源可视化区分

### Requirement: Context menu for edges and nodes
系统 SHALL 提供右键上下文菜单，支持对节点和连线的快捷操作。

#### Scenario: Edge context menu
- **WHEN** 用户右键点击一条 edge
- **THEN** 系统 SHALL 显示上下文菜单，包含“反转方向”和“删除连线”操作

#### Scenario: Reverse edge direction
- **WHEN** 用户在 edge 上下文菜单中选择“反转方向”
- **THEN** 系统 SHALL 创建 source/target 互换的新 edge，并重新映射 handle 标识

#### Scenario: Node context menu
- **WHEN** 用户右键点击一个节点
- **THEN** 系统 SHALL 显示上下文菜单，包含“删除节点”和“断开所有连线”操作

### Requirement: Fine-grained snap to grid
系统 SHALL 支持节点拖拽时吸附到细粒度网格，并在背景显示同样步长的点阵。

#### Scenario: Grid snapping enabled
- **WHEN** 用户拖拽节点
- **THEN** 系统 SHALL 将节点位置吸附到 4px 网格

#### Scenario: Grid visual
- **WHEN** 画布渲染背景
- **THEN** 系统 SHALL 显示与 4px snap 网格对齐的点阵背景

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
系统 SHALL 支持画布操作的撤销和重做，基于节点和连线 snapshot 栈。

#### Scenario: Undo last action
- **WHEN** 用户按下 Ctrl+Z
- **THEN** 系统 SHALL 恢复画布到上一个 snapshot 状态

#### Scenario: Redo undone action
- **WHEN** 用户按下 Ctrl+Shift+Z
- **THEN** 系统 SHALL 重新应用最近一次被撤销的 snapshot

#### Scenario: Snapshot stack limit
- **WHEN** snapshot 栈超过 50 条
- **THEN** 系统 SHALL 丢弃最早的 snapshot，保持栈深度 <= 50

#### Scenario: New action clears redo stack
- **WHEN** 用户在 undo 后执行新操作
- **THEN** 系统 SHALL 清空 redo 栈

### Requirement: Selected node neighborhood highlight
系统 SHALL 在用户点击 Canvas 上的节点时高亮该节点及其直接相连的一跳入边和出边，并弱化无关 edge。该高亮 SHALL 是渲染派生状态，不写入 DAG 配置。

#### Scenario: Highlight connected edges on node click
- **WHEN** 用户点击 Canvas 上的一个节点
- **THEN** 系统 SHALL 高亮该节点
- **AND** 系统 SHALL 高亮所有 `source` 或 `target` 等于该节点 ID 的 edge

#### Scenario: De-emphasize unrelated edges
- **WHEN** 用户点击 Canvas 上的一个节点
- **THEN** 系统 SHALL 降低与该节点不直接相连的 edge opacity

#### Scenario: Do not highlight unrelated edges
- **WHEN** 用户点击 Canvas 上的一个节点
- **THEN** 系统 SHALL NOT 高亮与该节点不直接相连的 edge

#### Scenario: Selection highlight does not override runtime path color
- **WHEN** DAG 存在运行态 edge 高亮且用户选中一个节点
- **THEN** 系统 SHALL 保留运行态 edge 颜色
- **AND** 系统 SHALL 仅用额外 stroke width、opacity 或 shadow 表达手动选中态
