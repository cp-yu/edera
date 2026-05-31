## MODIFIED Requirements

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
