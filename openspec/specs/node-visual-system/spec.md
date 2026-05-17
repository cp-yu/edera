## Purpose

定义 Workbench 节点视觉系统，覆盖类型差异化外观、动态 Handle、运行状态 badge 和节点分组可视化。

## Requirements

### Requirement: Type-differentiated node appearance
系统 SHALL 为不同类型的节点提供差异化的视觉外观，使大规模 DAG 场景下快速辨识节点类型。

#### Scenario: Fetcher node style
- **WHEN** 画布渲染 type 为 `fetcher` 的节点
- **THEN** 系统 SHALL 使用蓝色系配色和数据源图标

#### Scenario: LLM node style
- **WHEN** 画布渲染 type 为 `llm` 的节点
- **THEN** 系统 SHALL 使用紫色系配色和 AI 图标

#### Scenario: Aggregator node style
- **WHEN** 画布渲染 type 为 `aggregator` 的节点
- **THEN** 系统 SHALL 使用绿色系配色和汇聚图标

### Requirement: Dynamic handle generation
系统 SHALL 按节点连接关系动态生成 Handle，左侧为 input（target），右侧为 output（source）。

#### Scenario: Minimum handle availability
- **WHEN** 节点当前没有任何连线
- **THEN** 系统 SHALL 仍然提供至少 1 个左侧 input Handle 和 1 个右侧 output Handle

#### Scenario: Handle count follows connectivity
- **WHEN** 节点存在 N 条入边或出边
- **THEN** 系统 SHALL 在对应侧生成不少于 N 个 Handle，并保持均匀分布

#### Scenario: Unconnected handles stay discoverable
- **WHEN** 节点未被 hover 且某 Handle 尚未连接
- **THEN** 系统 SHALL 保持该 Handle 半可见，以便用户直接发起连线

#### Scenario: All handles visible on hover
- **WHEN** 用户将鼠标悬停在节点上
- **THEN** 系统 SHALL 显示该节点所有 Handle

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
