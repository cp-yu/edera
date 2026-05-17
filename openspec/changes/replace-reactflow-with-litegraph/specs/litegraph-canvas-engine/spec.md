## ADDED Requirements

### Requirement: LiteGraph canvas mounting
系统 SHALL 在 workbench 画布区域挂载 LiteGraph canvas 实例，通过 React ref 管理生命周期。

#### Scenario: Mount canvas on workbench load
- **WHEN** 用户进入 `/workbench` 页面
- **THEN** 系统 SHALL 创建 `LGraph` 和 `LGraphCanvas` 实例，挂载到画布区域的 `<canvas>` 元素

#### Scenario: Destroy canvas on unmount
- **WHEN** 用户离开 `/workbench` 页面
- **THEN** 系统 SHALL 销毁 `LGraphCanvas` 和 `LGraph` 实例，释放 canvas 资源

#### Scenario: Canvas resize follows container
- **WHEN** 浏览器窗口尺寸变化或容器布局改变
- **THEN** 画布 SHALL 自动匹配容器实际像素尺寸，交互坐标保持准确

### Requirement: Dynamic node type registration
系统 SHALL 根据后端返回的节点原型动态注册 LiteGraph 节点类型。

#### Scenario: Register node types from API
- **WHEN** 节点原型 API 返回数据
- **THEN** 系统 SHALL 遍历原型列表，为每个原型注册一个 `DynamicNode` 实例到 `LiteGraph.registerNodeType`，配置对应的 title、color 和 input/output slots

#### Scenario: Color by node type
- **WHEN** 节点注册时
- **THEN** 系统 SHALL 按 `node.type` 分配颜色（fetcher、llm、aggregator 各有预定义色值）

#### Scenario: Extensible node class
- **WHEN** 未来需要为特定类型添加差异化渲染
- **THEN** 系统 SHALL 支持通过继承 `DynamicNode` 基类注册特化节点类型，不影响现有统一注册逻辑

### Requirement: Canvas interaction
系统 SHALL 提供完整的节点图交互能力，包括节点拖拽、连线、删除、框选、缩放和平移。

#### Scenario: Drag node on canvas
- **WHEN** 用户在画布上拖动节点
- **THEN** 节点 SHALL 跟随鼠标移动，位置实时更新

#### Scenario: Connect nodes via port drag
- **WHEN** 用户从上游节点的 output slot 拖拽连线到下游节点的 input slot
- **THEN** 系统 SHALL 在两节点间创建连接

#### Scenario: Delete node or connection
- **WHEN** 用户选中节点或连线并按 Delete 键
- **THEN** 系统 SHALL 从 LGraph 中移除对应元素

#### Scenario: Box selection
- **WHEN** 用户在画布空白区域拖拽框选
- **THEN** 系统 SHALL 选中框内所有节点

#### Scenario: Zoom and pan
- **WHEN** 用户滚轮缩放或中键拖拽平移
- **THEN** 画布视口 SHALL 相应缩放或平移

### Requirement: Event bridge to React
系统 SHALL 将 LiteGraph canvas 事件桥接到 zustand store，使 React 侧边栏组件能响应画布状态变更。

#### Scenario: Node selected event
- **WHEN** 用户在画布中点击选中一个节点
- **THEN** 系统 SHALL 通过 `onNodeSelected` 回调更新 zustand `selectedNodeId`

#### Scenario: Node deselected event
- **WHEN** 用户点击画布空白区域取消选中
- **THEN** 系统 SHALL 通过 `onNodeDeselected` 回调清空 zustand `selectedNodeId`

#### Scenario: Connection change event
- **WHEN** 画布中连线被创建或删除
- **THEN** 系统 SHALL 通过 `onConnectionChange` 回调通知 adapter 层同步状态

### Requirement: CSS theming
系统 SHALL 通过 CSS 覆盖 LiteGraph 默认样式，匹配现有深色主题设计系统。

#### Scenario: Dark theme applied
- **WHEN** 画布渲染
- **THEN** 系统 SHALL 应用深色背景、现代字体和圆角样式，与 Tailwind 深色主题一致

#### Scenario: Node type color distinction
- **WHEN** 不同类型节点渲染
- **THEN** 系统 SHALL 按类型着色（保留现有 `blendTargetColors` 逻辑的色值映射）
