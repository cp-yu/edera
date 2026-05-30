## ADDED Requirements

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

## MODIFIED Requirements

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

