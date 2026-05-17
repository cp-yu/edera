# dag-workbench-ui Specification

## Purpose
定义 DAG Workbench 前端基础能力，覆盖三栏布局、节点面板、Inspector、底部工具栏，以及基于 React Flow 的图编辑主交互。
## Requirements
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
系统 SHALL 使用自定义 React Flow 节点组件，按节点连接关系动态生成左 input / 右 output Handle，并保留 target 颜色边框语义。

#### Scenario: Dynamic handles by connectivity
- **WHEN** 画布渲染节点
- **THEN** 系统 SHALL 根据当前连接关系动态生成左侧 target Handle 和右侧 source Handle

#### Scenario: Unconnected handles stay discoverable
- **WHEN** 节点未被 hover 且 Handle 尚未连接
- **THEN** 系统 SHALL 保持该 Handle 半可见，以便用户直接发起连线

#### Scenario: All handles visible on hover
- **WHEN** 用户将鼠标悬停在节点上
- **THEN** 系统 SHALL 显示该节点所有 Handle

#### Scenario: Single target node color
- **WHEN** 节点仅关联一个 target
- **THEN** 系统 SHALL 使用该 target 的预定义颜色作为节点左边框色

#### Scenario: Multi-target node color
- **WHEN** 节点关联多个 target
- **THEN** 系统 SHALL 使用各 target 颜色的 RGB 均值作为节点左边框色

### Requirement: Target filtering with opacity
系统 SHALL 在底部工具栏提供 target 多选过滤器，非匹配节点降低透明度。

#### Scenario: Filter by target
- **WHEN** 用户选择特定 target 进行过滤
- **THEN** 系统 SHALL 将不包含该 target 的节点 opacity 降至 0.2，匹配节点保持 1.0

#### Scenario: Clear filter
- **WHEN** 用户清除所有 target 过滤
- **THEN** 系统 SHALL 恢复所有节点为完全不透明

### Requirement: Edge arrows and visual feedback
系统 SHALL 在所有连接线末端显示箭头标记，并在运行时提供执行路径视觉反馈。

#### Scenario: Edge arrow marker
- **WHEN** 画布渲染连接线
- **THEN** 系统 SHALL 在 edge 的 target 端显示闭合箭头（MarkerType.ArrowClosed）

#### Scenario: Running path highlight
- **WHEN** DAG 正在运行
- **THEN** 系统 SHALL 对活跃执行路径 edge 加粗并按节点状态着色

### Requirement: Interactive edge management
系统 SHALL 支持用户在画布上通过 Handle 交互新增连线，以及选中连线后删除。

#### Scenario: Connect nodes via handle drag
- **WHEN** 用户从一个节点的 source Handle 拖拽连线到另一个节点的 target Handle
- **THEN** 系统 SHALL 创建新的 edge 并添加到画布，记录 sourceHandle 和 targetHandle 标识

#### Scenario: Delete edge with keyboard
- **WHEN** 用户选中一条 edge 并按下 Delete 键
- **THEN** 系统 SHALL 从画布中移除该 edge

### Requirement: Node position persistence
系统 SHALL 在用户拖拽节点后自动持久化位置，采用 localStorage 草稿 + debounce 写后端的混合策略。

#### Scenario: Auto-save on drag stop
- **WHEN** 用户拖拽节点并释放
- **THEN** 系统 SHALL 立即将当前所有节点位置写入 localStorage 作为草稿

#### Scenario: Debounce save to backend
- **WHEN** 节点拖拽停止后 500ms 内无新的拖拽操作
- **THEN** 系统 SHALL 调用 `PUT /api/graph/dag/{name}` 将完整 UI + 拓扑持久化到后端

#### Scenario: Restore from localStorage on load
- **WHEN** 画布加载 DAG 且 localStorage 中存在该 DAG 的草稿位置
- **THEN** 系统 SHALL 优先使用 localStorage 中的位置数据

#### Scenario: Clear localStorage after backend save
- **WHEN** 后端保存成功
- **THEN** 系统 SHALL 清除该 DAG 在 localStorage 中的草稿数据

### Requirement: Auto-layout tool
系统 SHALL 提供自动布局工具按钮，使用 ELK layered 算法计算分层布局。

#### Scenario: Trigger auto-layout
- **WHEN** 用户点击自动布局按钮
- **THEN** 系统 SHALL 使用 ELK layered 算法重新计算所有节点位置并更新画布

#### Scenario: Layout direction
- **WHEN** 自动布局执行
- **THEN** 系统 SHALL 默认使用 DOWN 方向排布

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
