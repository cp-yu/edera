## ADDED Requirements

### Requirement: Alias-first Canvas node title
Canvas 中的自定义节点 SHALL 使用实例 `alias` 作为主标题；当 `alias` 为空时，系统 SHALL 回退显示 `type_name`。系统 MUST 保留真实 `type_name` 作为副信息，避免 alias 重名时无法确认节点类型。

#### Scenario: Canvas title uses alias
- **WHEN** DAG 节点实例包含非空 `alias`
- **THEN** Canvas 节点卡片标题 SHALL 显示该 `alias`
- **AND** 节点卡片 SHALL 同时显示该实例的 `type_name` 作为副信息

#### Scenario: Canvas title falls back to type_name
- **WHEN** DAG 节点实例没有 `alias` 或 `alias` 为空
- **THEN** Canvas 节点卡片标题 SHALL 显示该实例的 `type_name`

#### Scenario: Alias display does not change identity
- **WHEN** Canvas 使用 `alias` 显示节点标题
- **THEN** 系统 MUST 继续使用节点实例 UUID 作为 edge 的 `from` 和 `to` 引用
