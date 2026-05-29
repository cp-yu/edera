## ADDED Requirements

### Requirement: Inspector Triggers tab 入口

DAG 工作台 Inspector SHALL 在现有 `Config | Runtime` tab 之外增加 `Triggers` tab。

#### Scenario: Inspector 显示 Triggers tab

- **WHEN** 用户进入 Workbench 页面
- **THEN** Inspector 面板显示三个 tab：`Config`、`Runtime`、`Triggers`

#### Scenario: 无选中时 Triggers tab 显示 DAG 级 trigger

- **WHEN** 用户未选中任何 node 或 edge，切换到 Triggers tab
- **THEN** 显示当前 DAG 的所有 trigger 列表（`target = dag:{dagName}`）
