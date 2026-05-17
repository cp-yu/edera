## ADDED Requirements

### Requirement: Type-differentiated node appearance
系统 SHALL 为不同类型的节点提供差异化的视觉外观，使 30+ 节点场景下快速辨识节点类型。

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
系统 SHALL 按节点类型和端口语义动态生成 Handle，左侧为 input（target），右侧为 output（source）。

#### Scenario: Input handles on left
- **WHEN** 节点有 N 个上游连接
- **THEN** 系统 SHALL 在节点左侧均匀分布 N 个 target Handle

#### Scenario: Output handles on right
- **WHEN** 节点有 M 个下游连接
- **THEN** 系统 SHALL 在节点右侧均匀分布 M 个 source Handle

#### Scenario: Minimum handles
- **WHEN** 节点无已有连接
- **THEN** 系统 SHALL 至少显示 1 个 target Handle（左）和 1 个 source Handle（右）

#### Scenario: Handle visibility on hover
- **WHEN** 用户将鼠标悬停在节点上
- **THEN** 系统 SHALL 显示所有 Handle；鼠标离开后隐藏未连接的 Handle

### Requirement: Runtime status badge
系统 SHALL 在节点上显示轻量状态 badge，指示运行状态。

#### Scenario: Succeeded status
- **WHEN** 节点运行状态为 `succeeded`
- **THEN** 系统 SHALL 在节点左上角显示绿色圆点 badge

#### Scenario: Running status
- **WHEN** 节点运行状态为 `running`
- **THEN** 系统 SHALL 在节点左上角显示蓝色圆点 badge 并附带 pulse 动画

#### Scenario: Pending status
- **WHEN** 节点运行状态为 `pending`
- **THEN** 系统 SHALL 在节点左上角显示灰色圆点 badge

#### Scenario: Failed status
- **WHEN** 节点运行状态为 `failed`
- **THEN** 系统 SHALL 在节点左上角显示红色圆点 badge

#### Scenario: No runtime status
- **WHEN** 节点无运行状态数据
- **THEN** 系统 SHALL 不显示 badge

### Requirement: Target-based group visualization
系统 SHALL 按节点关联的 target 自动推导分组，并在画布上用视觉分区表示。

#### Scenario: Group background rendering
- **WHEN** 画布渲染时存在多个 target 分组
- **THEN** 系统 SHALL 为每个分组绘制半透明背景色块，包围该组所有节点

#### Scenario: Group color assignment
- **WHEN** 系统计算分组可视化
- **THEN** 系统 SHALL 为每个 target 分配唯一的背景色，与该 target 的预定义颜色一致

#### Scenario: Ungrouped nodes
- **WHEN** 节点未关联任何 target
- **THEN** 系统 SHALL 不为该节点绘制分组背景
