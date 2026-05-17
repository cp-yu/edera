## MODIFIED Requirements

### Requirement: Three-column workbench layout
系统 SHALL 提供固定三栏布局：左侧 Palette（250px）、中间 LiteGraph Canvas（弹性宽度）、右侧 Inspector（300px），底部工具栏（40px）。

#### Scenario: Render workbench layout
- **WHEN** 用户进入 `/workbench` 页面
- **THEN** 系统 SHALL 渲染三栏布局，中间区域挂载 LiteGraph `<canvas>` 元素占据剩余空间

### Requirement: Node palette with drag-to-add
系统 SHALL 在左侧面板展示可用节点列表，支持拖拽到 LiteGraph canvas 添加节点。

#### Scenario: Drag node to canvas
- **WHEN** 用户从 Palette 拖拽一个节点到画布
- **THEN** 系统 SHALL 监听 canvas 元素的 `drop` 事件，在鼠标释放的画布坐标处调用 `LGraph.add(new DynamicNode(...))` 创建节点实例

#### Scenario: Drop position accuracy
- **WHEN** 用户在画布任意位置释放拖拽的节点
- **THEN** 系统 SHALL 将屏幕坐标转换为 LiteGraph canvas 坐标，节点出现在鼠标释放位置

#### Scenario: Group nodes by type
- **WHEN** Palette 加载节点列表
- **THEN** 系统 SHALL 按节点类型分组展示（LLM 节点、功能节点等）

### Requirement: Node position persistence
系统 SHALL 持久化用户手动拖拽的节点位置，通过手动保存写回后端。

#### Scenario: Drag node preserves position
- **WHEN** 用户拖拽节点到新位置
- **THEN** 系统 SHALL 在 LGraph 内部更新节点位置，不触发后端请求

#### Scenario: Position saved on manual save
- **WHEN** 用户点击保存按钮
- **THEN** 系统 SHALL 通过 adapter 将所有节点当前位置导出到 `ui.nodes` 元数据并写回后端

### Requirement: Auto-layout tool
系统 SHALL 提供自动布局工具按钮，使用 LiteGraph 内置或外部算法计算层级布局。

#### Scenario: Trigger auto-layout
- **WHEN** 用户点击自动布局按钮
- **THEN** 系统 SHALL 重新计算所有节点位置并更新 LGraph 节点坐标

#### Scenario: Layout direction
- **WHEN** 自动布局执行
- **THEN** 系统 SHALL 默认使用 TB（top-bottom）方向排布

## ADDED Requirements

### Requirement: Manual save with draft
系统 SHALL 提供手动保存按钮，替代原有的操作即保存策略。

#### Scenario: Manual save triggers API write
- **WHEN** 用户点击保存按钮
- **THEN** 系统 SHALL 调用 adapter `toDag()` 导出 LGraph 状态，通过 API 写回后端 DAG yaml

#### Scenario: Unsaved changes indicator
- **WHEN** LGraph 状态与上次保存状态不一致
- **THEN** 系统 SHALL 在工具栏显示未保存标记

## REMOVED Requirements

### Requirement: Custom node rendering with target colors
**Reason**: ReactFlow 自定义节点组件（CustomNode.tsx）被 LiteGraph canvas 原生渲染替代。节点颜色区分通过 LiteGraph node color 属性实现。
**Migration**: 节点类型颜色映射迁移到 DynamicNode 注册时的 color 参数。`blendTargetColors` 逻辑迁移到 LiteGraph node 的 `bgcolor` 属性。

### Requirement: Edge arrows and visual feedback
**Reason**: ReactFlow edge 样式（MarkerType.ArrowClosed、animated）被 LiteGraph 原生连线渲染替代。LiteGraph 连线自带方向箭头和路由。
**Migration**: 运行时动画效果通过 LiteGraph link color/thickness 动态修改实现。
