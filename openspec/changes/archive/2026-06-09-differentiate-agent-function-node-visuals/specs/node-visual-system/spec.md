## MODIFIED Requirements

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
