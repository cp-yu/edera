## Purpose

定义 DAG 统一工作台前端能力，覆盖三栏布局、React Flow 画布、节点 Palette、Inspector 编辑面板、底部工具栏、Target 过滤、节点颜色映射、内联创建和全局保存警告。

## ADDED Requirements

### Requirement: Three-column workbench layout
系统 SHALL 提供固定三栏布局：左侧 Palette（250px）、中间 React Flow Canvas（弹性宽度）、右侧 Inspector（300px），底部工具栏（40px）。

#### Scenario: Render workbench layout
- **WHEN** 用户进入 `/workbench` 页面
- **THEN** 系统 SHALL 渲染三栏布局，画布占据剩余空间

### Requirement: DAG selector and switching
系统 SHALL 在底部工具栏提供 DAG 选择器，切换 DAG 时刷新所有面板数据。

#### Scenario: Switch DAG
- **WHEN** 用户在底部工具栏选择不同的 DAG
- **THEN** 系统 SHALL 重新加载该 DAG 的拓扑、节点配置和运行状态，画布重新渲染

### Requirement: Node palette with drag-to-add
系统 SHALL 在左侧面板展示可用节点列表，支持拖拽到画布添加节点引用。

#### Scenario: Drag node to canvas
- **WHEN** 用户从 Palette 拖拽一个节点到画布
- **THEN** 系统 SHALL 将该节点添加到当前 DAG 的拓扑中（未保存状态）

#### Scenario: Group nodes by type
- **WHEN** Palette 加载节点列表
- **THEN** 系统 SHALL 按节点类型分组展示（Fetchers、Analyzers、Generators 等）

### Requirement: Custom node rendering with target colors
系统 SHALL 使用自定义 React Flow 节点组件，根据节点关联的 target 显示颜色。

#### Scenario: Single target node color
- **WHEN** 节点仅关联一个 target
- **THEN** 系统 SHALL 使用该 target 的预定义颜色作为节点左边框色

#### Scenario: Multi-target node color
- **WHEN** 节点关联多个 target
- **THEN** 系统 SHALL 使用各 target 颜色的 RGB 均值作为节点左边框色，并显示多色指示

### Requirement: Target filtering with opacity
系统 SHALL 在底部工具栏提供 target 多选过滤器，非匹配节点降低透明度。

#### Scenario: Filter by target
- **WHEN** 用户选择特定 target 进行过滤
- **THEN** 系统 SHALL 将不包含该 target 的节点 opacity 降至 0.2，匹配节点保持 1.0

#### Scenario: Clear filter
- **WHEN** 用户清除所有 target 过滤
- **THEN** 系统 SHALL 恢复所有节点为完全不透明

### Requirement: Node inspector with editable/readonly fields
系统 SHALL 在右侧 Inspector 面板展示选中节点的配置，区分可编辑和只读字段。

#### Scenario: Select node and show inspector
- **WHEN** 用户在画布上点击一个节点
- **THEN** 系统 SHALL 在 Inspector 中展示该节点的配置表单

#### Scenario: Edit runtime parameters
- **WHEN** 用户修改 Inspector 中的 `name`、`source_names`、`timeout_seconds` 或 `parameters` 字段
- **THEN** 系统 SHALL 允许编辑并标记为未保存状态

#### Scenario: Readonly identity fields
- **WHEN** Inspector 展示节点的 `type`、`skills`、`input_type`、`output_type` 字段
- **THEN** 系统 SHALL 以只读方式展示，不允许编辑

### Requirement: Global save warning
系统 SHALL 在保存节点配置时警告用户该节点为全局实例。

#### Scenario: Save node with warning
- **WHEN** 用户点击 Inspector 中的"保存节点"按钮
- **THEN** 系统 SHALL 弹出确认对话框，提示"此节点为全局实例，修改将影响所有引用它的 DAG"

### Requirement: New fetcher creation
系统 SHALL 在 Palette 底部提供创建新 Fetcher 实例的入口。

#### Scenario: Create new fetcher
- **WHEN** 用户点击 Palette 中的"+ New Fetcher"按钮
- **THEN** 系统 SHALL 打开创建面板，提供 skeleton 预设选择（RSS Fetcher / Web Fetcher）

#### Scenario: Auto-add created fetcher to canvas
- **WHEN** 用户完成新 Fetcher 创建
- **THEN** 系统 SHALL 将新节点自动添加到当前 DAG 画布并选中

### Requirement: Inline source instance creation
系统 SHALL 在 Inspector 中提供内联创建信息源实例的入口。

#### Scenario: Create source inline
- **WHEN** 用户在 Inspector 中点击"+ New Input Source"
- **THEN** 系统 SHALL 打开内联表单（仅 name + url），type 固定为当前 fetcher 类型

#### Scenario: Auto-bind created source
- **WHEN** 用户完成内联信息源创建
- **THEN** 系统 SHALL 将新信息源写入 portfolio 并自动添加到当前 fetcher 的 `source_names`

### Requirement: Run control in toolbar
系统 SHALL 在底部工具栏提供当前 DAG 的运行/停止控制和状态显示。

#### Scenario: Run current DAG
- **WHEN** 用户点击底部工具栏的"运行"按钮
- **THEN** 系统 SHALL 触发当前选中 DAG 的运行，按钮变为"停止"，状态指示器显示 running

#### Scenario: Poll runtime status
- **WHEN** DAG 正在运行
- **THEN** 系统 SHALL 每 2 秒轮询运行状态，画布上对应节点显示实时执行状态（pulse 动画）

#### Scenario: Run completion notification
- **WHEN** DAG 运行完成
- **THEN** 系统 SHALL 停止轮询，显示 toast 通知运行结果，状态指示器更新
