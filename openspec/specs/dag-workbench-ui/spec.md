---
capabilities:
  - cap.web.dag-workbench-ui
---
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
系统 SHALL 在底部工具栏提供 DAG 选择器，切换 DAG 时刷新所有面板数据。系统 SHALL 将用户最后选中的 DAG 名称持久化为浏览器本地 Workbench 状态，并在用户再次进入 `/workbench` 时优先恢复该 DAG。

#### Scenario: Switch DAG
- **WHEN** 用户在底部工具栏选择不同的 DAG
- **THEN** 系统 SHALL 重新加载该 DAG 的拓扑、节点配置和运行状态，画布重新渲染

#### Scenario: Persist selected DAG
- **WHEN** 用户在 Workbench 中选择 DAG `analysis`
- **THEN** 系统 SHALL 将 `analysis` 保存为浏览器本地的最后选中 DAG

#### Scenario: Restore last selected DAG
- **WHEN** 用户再次进入 `/workbench` 且浏览器本地存在最后选中 DAG `analysis`
- **THEN** 系统 SHALL 默认加载并显示 DAG `analysis`

### Requirement: Node palette with drag-to-add
系统 SHALL 在左侧面板按 role 分组展示可用节点类型（Sources / Processors / Sinks），并在每个 role 分组内按节点名称前缀做二级分组。系统 SHALL 支持拖拽到画布创建节点实例。画布 SHALL 允许同一节点类型被多次拖入，每次创建独立实例。节点面板 SHALL 支持搜索和临时折叠，折叠状态 SHALL 只在当前页面会话内生效。

#### Scenario: Grouped display by role and prefix
- **WHEN** 用户打开 Palette 面板
- **THEN** 系统 SHALL 将节点类型按 `role` 分为 Sources、Processors、Sinks
- **AND** 系统 SHALL 在每个 `role` 组内按节点名称前缀显示二级分组

#### Scenario: Drag to create instance
- **WHEN** 用户将节点类型从 Palette 拖入画布
- **THEN** 系统 SHALL 创建一个新的节点实例（生成 UUID），而非引用类型本身

#### Scenario: Multiple instances of same type
- **WHEN** 用户将同一节点类型拖入画布多次
- **THEN** 系统 SHALL 为每次拖入创建独立实例（不同 UUID），不做去重限制

#### Scenario: Search matches type name and instance alias
- **WHEN** 用户在 Palette 搜索框输入关键词
- **THEN** 系统 SHALL 同时匹配节点类型名称和当前 DAG 中已有实例的别名

#### Scenario: Search shows matching groups
- **WHEN** 用户在 Palette 搜索框输入关键词且匹配某个折叠分组内的节点类型
- **THEN** 系统 SHALL 展示匹配的节点类型，不因该分组处于折叠状态而隐藏结果

#### Scenario: Collapse palette group
- **WHEN** 用户折叠 Palette 的 role 组或 prefix 组
- **THEN** 系统 SHALL 隐藏该组下的节点类型列表

#### Scenario: Palette collapse state is session-local
- **WHEN** 用户刷新或重新打开 Workbench 页面
- **THEN** Palette 折叠状态 SHALL 恢复为默认展开状态

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

系统 SHALL 将底部工具栏的 target 过滤器替换为 entity 过滤器，支持按任意 entity type 过滤。

#### Scenario: Filter by entity

- **WHEN** 用户在底部工具栏选择特定 entity 进行过滤
- **THEN** 系统 SHALL 将不包含该 entity 的节点 opacity 降至 0.2，匹配节点保持 1.0

#### Scenario: Entity filter shows all types

- **WHEN** 用户打开 entity 过滤器
- **THEN** 系统 SHALL 显示所有 entity types 的实体（不仅限于 stock）

#### Scenario: Clear entity filter

- **WHEN** 用户清除所有 entity 过滤
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
系统 SHALL 在右侧 Inspector 面板根据节点类型展示差异化的编辑字段。Config tab 中的实例保存动作 SHALL 固定显示在 Inspector 可视域底部。

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

#### Scenario: Config save remains visible
- **WHEN** 用户在 Inspector Config tab 中滚动长表单
- **THEN** 系统 SHALL 保持“保存实例”动作固定显示在 Inspector 可视域底部

#### Scenario: Non-config tabs do not show instance save footer
- **WHEN** 用户切换到 Runtime 或 Triggers tab
- **THEN** 系统 SHALL NOT 显示 Config tab 的“保存实例”固定 footer

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

### Requirement: Edge configuration in Inspector
系统 SHALL 在用户选中画布上的边时，在 Inspector 面板展示边的配置选项。

#### Scenario: Select edge shows config
- **WHEN** 用户点击画布上的一条边
- **THEN** 系统 SHALL 在 Inspector 面板切换为边配置视图，展示 `fan_in`、`fan_out` 和 `optional` 开关

#### Scenario: Toggle fan_in
- **WHEN** 用户在边配置面板中切换 `fan_in` 开关
- **THEN** 系统 SHALL 更新该边的 `fan_in` 属性并持久化到 DAG YAML

#### Scenario: Toggle fan_out
- **WHEN** 用户在边配置面板中切换 `fan_out` 开关
- **THEN** 系统 SHALL 更新该边的 `fan_out` 属性并持久化到 DAG YAML

#### Scenario: Toggle optional
- **WHEN** 用户在边配置面板中切换 `optional` 开关
- **THEN** 系统 SHALL 更新该边的 `optional` 属性并持久化到 DAG YAML

### Requirement: Inspector entity selector

系统 SHALL 在 Inspector 中提供实体选择器，支持按类型分组、搜索过滤、优先显示关联实体。

#### Scenario: Display entity selector

- **WHEN** 用户在 Inspector 中选择节点
- **THEN** 系统 SHALL 显示实体选择器，类似 skills 的多选组件

#### Scenario: Group entities by type

- **WHEN** 实体选择器展开
- **THEN** 系统 SHALL 按 entity type 分组显示实体（如 "股票"、"信息源"）

#### Scenario: Prioritize related entities

- **WHEN** 节点配置了 source，且 `entity-relations.yaml` 中有关联关系
- **THEN** 系统 SHALL 在选择器顶部优先显示关联的实体

#### Scenario: Search entities

- **WHEN** 用户在实体选择器中输入搜索关键词
- **THEN** 系统 SHALL 过滤显示匹配的实体（匹配 display_template 渲染结果）

#### Scenario: Save selected entities

- **WHEN** 用户选择实体后点击保存
- **THEN** 系统 SHALL 将 `entities` 字段保存到节点的 `config` 中

### Requirement: Inspector permission overrides

系统 SHALL 在 Inspector 中提供权限覆盖配置器，仅展示当前节点已选 entities 对应的 entity type 的权限字段，支持按需添加字段权限提权。

#### Scenario: Filter by selected entities

- **WHEN** 节点已选择 entities（如 `["stock:AAPL", "web-source:reuters"]`）
- **THEN** 系统 SHALL 仅展示 `stock` 和 `web-source` 两个 entity type 的权限字段

#### Scenario: No entities selected

- **WHEN** 节点未选择任何 entity
- **THEN** 系统 SHALL 不展示权限配置器，或展示空状态提示

#### Scenario: Entity deselection cleans permissions

- **WHEN** 用户取消选择某个 entity，导致其 type 不再被任何已选 entity 引用
- **THEN** 系统 SHALL 自动清除该 type 的 permission overrides

#### Scenario: Add permission override

- **WHEN** 用户点击"添加权限覆盖"按钮
- **THEN** 系统 SHALL 显示字段选择器和权限选择器

#### Scenario: Select field to override

- **WHEN** 用户在字段选择器中选择 entity type 和字段
- **THEN** 系统 SHALL 显示该字段的默认权限和可选的提权选项

#### Scenario: Select permission level

- **WHEN** 用户选择权限级别
- **THEN** 系统 SHALL 验证是否为合法提权（不能降权）

#### Scenario: Save permission overrides

- **WHEN** 用户点击保存
- **THEN** 系统 SHALL 将 `entity_permissions` 字段保存到节点的 `config` 中

#### Scenario: Remove permission override

- **WHEN** 用户点击权限覆盖条目的删除按钮
- **THEN** 系统 SHALL 从配置中移除该字段的权限覆盖

### Requirement: Grouped entity filter selector
系统 SHALL 在 Workbench 底部工具栏提供紧凑的 entity 分组多选过滤器，避免所有 item 横向铺开。

#### Scenario: Show compact entity filter summary
- **WHEN** 当前 DAG 存在多个 entity
- **THEN** 系统 SHALL 在底部工具栏显示一个固定入口和当前选择摘要，而不是直接横向显示全部 entity item

#### Scenario: Group entity filter items
- **WHEN** 用户展开底部 entity 过滤器
- **THEN** 系统 SHALL 按 `entity.type` 分组显示可选 entity item

#### Scenario: Toggle grouped entity filter item
- **WHEN** 用户在分组面板中选择或取消选择 entity item
- **THEN** 系统 SHALL 更新现有 `entityFilter` 多选状态，并保持画布按已选 entity 过滤

#### Scenario: Clear grouped entity filter
- **WHEN** 用户点击清除入口
- **THEN** 系统 SHALL 清空 `entityFilter` 并恢复显示全部节点

### Requirement: Inspector Triggers tab 入口

DAG 工作台 Inspector SHALL 在现有 `Config | Runtime` tab 之外增加 `Triggers` tab。

#### Scenario: Inspector 显示 Triggers tab

- **WHEN** 用户进入 Workbench 页面
- **THEN** Inspector 面板显示三个 tab：`Config`、`Runtime`、`Triggers`

#### Scenario: 无选中时 Triggers tab 显示 DAG 级 trigger

- **WHEN** 用户未选中任何 node 或 edge，切换到 Triggers tab
- **THEN** 显示当前 DAG 的所有 trigger 列表（`target = dag:{dagName}`）

### Requirement: Node instance optional configuration in Inspector
系统 SHALL 在用户选中画布上的节点实例时，在 Inspector 面板提供当前 DAG 节点实例的 `optional` 配置入口。该入口 SHALL 写入 `DagNodeInstance.optional`，含义为当前实例的所有出边均视为 optional。Workbench MUST NOT 通过该入口修改全局 `NodeConfig.optional`。

#### Scenario: Select node shows instance optional
- **WHEN** 用户点击画布上的节点实例
- **THEN** Inspector SHALL 展示当前实例的 `optional` 开关
- **AND** 文案 SHALL 表达其作用范围为当前 DAG 当前实例

#### Scenario: Toggle node instance optional
- **WHEN** 用户在节点 Inspector 中切换 `optional` 开关
- **THEN** 系统 SHALL 更新该 DAG 节点实例的 `optional` 属性并持久化到 DAG YAML
- **AND** SHALL NOT 修改该节点类型的全局 NodeConfig

