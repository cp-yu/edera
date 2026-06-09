---
capabilities:
  - cap.web.node-visual-system
---
# node-visual-system Specification

## Purpose

定义 Workbench 节点视觉系统，覆盖类型差异化外观、动态 Handle、运行状态 badge 和节点分组可视化。
## Requirements
### Requirement: Type-differentiated node appearance
系统 SHALL 按节点 `type` 提供差异化视觉外观，使 function、agent、dag、wait 节点在 Workbench Canvas 中可快速辨识。节点 `role` SHALL NOT 改变视觉家族；`role` 仅用于 Handle 拓扑和 Palette 分组。

#### Scenario: Function node style
- **WHEN** 画布渲染 `type: function` 的节点
- **THEN** 系统 SHALL 使用 function 视觉家族的图标、配色和卡片样式

#### Scenario: Agent node style
- **WHEN** 画布渲染 `type: agent` 的节点
- **THEN** 系统 SHALL 使用不同于 function 的 agent 视觉家族图标、配色和卡片样式

#### Scenario: DAG node style
- **WHEN** 画布渲染 `type: dag` 的节点
- **THEN** 系统 SHALL 使用 dag 视觉家族的图标、配色和卡片样式

#### Scenario: Wait node style
- **WHEN** 画布渲染 `type: wait` 的节点
- **THEN** 系统 SHALL 使用 wait 视觉家族的图标、配色和卡片样式

#### Scenario: Role does not change visual family
- **WHEN** 画布分别渲染 `role: source`、`role: processor`、`role: sink` 且 `type` 相同的节点
- **THEN** 系统 SHALL 保持相同的视觉家族

#### Scenario: Agent intervention remains available
- **WHEN** 画布渲染 `type: agent` 的节点
- **THEN** 系统 SHALL 保留 agent intervention 入口

### Requirement: Dynamic handle generation
系统 SHALL 根据节点 role 和连接关系动态生成 Handle：source 节点仅生成输出 Handle，sink 节点仅生成输入 Handle，processor 节点两侧均生成。节点 `type` SHALL NOT 改变 Handle 拓扑。

#### Scenario: Source node handle generation
- **WHEN** 画布渲染 `role: source` 的节点
- **THEN** 系统 SHALL 仅在右侧生成输出 Handle，左侧不生成任何 Handle

#### Scenario: Sink node handle generation
- **WHEN** 画布渲染 `role: sink` 的节点
- **THEN** 系统 SHALL 仅在左侧生成输入 Handle，右侧不生成任何 Handle

#### Scenario: Processor handle count follows connectivity
- **WHEN** processor 节点存在 N 条入边或出边
- **THEN** 系统 SHALL 在对应侧生成不少于 N 个 Handle，并保持均匀分布

#### Scenario: Handle topology remains role-driven
- **WHEN** function 与 agent 节点具有相同 `role` 和连接关系
- **THEN** 系统 SHALL 为它们生成相同的 Handle 拓扑

### Requirement: Runtime status badge
系统 SHALL 在节点左上角显示轻量运行状态 badge。

#### Scenario: Running status
- **WHEN** 节点运行状态为 `running`
- **THEN** 系统 SHALL 显示蓝色圆点并带 pulse 动画

#### Scenario: Succeeded status
- **WHEN** 节点运行状态为 `succeeded`
- **THEN** 系统 SHALL 显示绿色圆点 badge

#### Scenario: Failed status
- **WHEN** 节点运行状态为 `failed`
- **THEN** 系统 SHALL 显示红色圆点 badge

#### Scenario: No runtime status
- **WHEN** 节点无运行状态数据
- **THEN** 系统 SHALL 不显示 badge

### Requirement: Source group visualization
系统 SHALL 按节点关联的 source 集合自动推导分组，并在画布上用视觉分区表示。

#### Scenario: Group background rendering
- **WHEN** 画布渲染时存在多个 source 分组
- **THEN** 系统 SHALL 为每个分组绘制半透明背景色块，包围该组所有节点

#### Scenario: Group color assignment
- **WHEN** 系统计算分组可视化
- **THEN** 系统 SHALL 为每个 source 分配唯一背景色，并与该 source 的预定义颜色一致

#### Scenario: Ungrouped nodes
- **WHEN** 节点未关联任何 source
- **THEN** 系统 SHALL 不为该节点绘制分组背景

### Requirement: Connection validation visual feedback
系统 SHALL 在拖拽连线过程中通过 Handle 颜色变化提供类型兼容性的实时视觉反馈。

#### Scenario: Compatible target — green highlight
- **WHEN** 用户拖拽连线经过一个类型兼容的目标 Handle
- **THEN** 系统 SHALL 将该 Handle 高亮为绿色

#### Scenario: Incompatible target — red highlight
- **WHEN** 用户拖拽连线经过一个类型不兼容的目标 Handle（Function 节点）
- **THEN** 系统 SHALL 将该 Handle 高亮为红色

#### Scenario: Warning connection line style
- **WHEN** 一条已建立的连线存在类型不匹配警告（LLM 节点目标）
- **THEN** 系统 SHALL 将该连线渲染为黄色虚线样式

### Requirement: Alias-first Canvas node title
Canvas 中的自定义节点 SHALL 使用实例 `alias` 作为主标题；当 `alias` 为空时，系统 SHALL 回退显示 `type_name`。系统 MUST 保留真实 `type_name` 作为副信息，避免 alias 重名时无法确认节点类型。

#### Scenario: Canvas title uses alias
- **WHEN** DAG 节点实例包含非空 `alias`
- **THEN** Canvas 节点卡片标题 SHALL 显示该 `alias`
- **AND** 节点卡片 SHALL 同时显示该实例的 `type_name` 作为副信息

#### Scenario: Canvas title falls back to type_name
- **WHEN** DAG 节点实例没有 `alias` 或 `alias` 为空
- **THEN** Canvas 节点卡片标题 SHALL 显示该实例的 `type_name`

#### Scenario: Alias display does not change identity
- **WHEN** Canvas 使用 `alias` 显示节点标题
- **THEN** 系统 MUST 继续使用节点实例 UUID 作为 edge 的 `from` 和 `to` 引用

