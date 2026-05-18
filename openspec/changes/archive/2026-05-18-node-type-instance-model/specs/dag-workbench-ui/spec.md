## MODIFIED Requirements

### Requirement: Node palette with drag-to-add
系统 SHALL 在左侧面板按 role 分组展示可用节点类型（Sources / Processors / Sinks），支持拖拽到画布创建节点实例。画布 SHALL 允许同一节点类型被多次拖入，每次创建独立实例。

#### Scenario: Grouped display by role
- **WHEN** 用户打开 Palette 面板
- **THEN** 系统 SHALL 将节点类型按 `role` 分为三组展示：Sources、Processors、Sinks

#### Scenario: Drag to create instance
- **WHEN** 用户将节点类型从 Palette 拖入画布
- **THEN** 系统 SHALL 创建一个新的节点实例（生成 UUID），而非引用类型本身

#### Scenario: Multiple instances of same type
- **WHEN** 用户将同一节点类型拖入画布多次
- **THEN** 系统 SHALL 为每次拖入创建独立实例（不同 UUID），不做去重限制

#### Scenario: Search matches type name and instance alias
- **WHEN** 用户在 Palette 搜索框输入关键词
- **THEN** 系统 SHALL 同时匹配节点类型名称和当前 DAG 中已有实例的别名

## ADDED Requirements

### Requirement: Edge configuration in Inspector
系统 SHALL 在用户选中画布上的边时，在 Inspector 面板展示边的配置选项。

#### Scenario: Select edge shows config
- **WHEN** 用户点击画布上的一条边
- **THEN** 系统 SHALL 在 Inspector 面板切换为边配置视图，展示 `fan_in` 和 `fan_out` 开关

#### Scenario: Toggle fan_in
- **WHEN** 用户在边配置面板中切换 `fan_in` 开关
- **THEN** 系统 SHALL 更新该边的 `fan_in` 属性并持久化到 DAG YAML

#### Scenario: Toggle fan_out
- **WHEN** 用户在边配置面板中切换 `fan_out` 开关
- **THEN** 系统 SHALL 更新该边的 `fan_out` 属性并持久化到 DAG YAML
