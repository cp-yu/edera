## MODIFIED Requirements

### Requirement: Inspector Triggers tab

Web Console 的 Workbench Inspector SHALL 在 `Config | Runtime` 之外增加 `Triggers` tab。Tab 内容根据当前选中目标切换：

- 无选中（canvas 空白）→ 显示 DAG 级 trigger 列表（`target = dag:{name}`）
- 选中 node → 显示 node 级 trigger 列表（`target = node:{dag_name}/{node_id}`）

#### Scenario: 无选中显示 DAG 级 trigger

- **WHEN** 用户进入 Workbench 选中 DAG `default` 但未选中任何 node
- **THEN** Inspector 显示 `Triggers` tab，列出所有 `target = "dag:default"` 的 trigger entity

#### Scenario: 选中 node 显示 DAG-scoped node 级 trigger

- **WHEN** 用户在 DAG `default` 的 Canvas 中点击某 node `<node-id>`
- **THEN** Inspector 切换到 node 视图，`Triggers` tab 列出所有 `target = "node:default/<node-id>"` 的 trigger entity

#### Scenario: 切换目标后 trigger 列表更新

- **WHEN** 用户从一个 node 切换选中到另一个 node
- **THEN** Triggers tab 列表立即刷新为新 node 的 DAG-scoped trigger 列表

### Requirement: trigger CRUD 操作

Triggers tab SHALL 支持创建、编辑、删除、启用/禁用 trigger entity。创建 node 级 trigger 时，系统 SHALL 自动设置 target 为 `node:{dag_name}/{node_id}`。

#### Scenario: 创建新 trigger

- **WHEN** 用户在 Triggers tab 点击"新建"按钮，填写表达式和 target，点击"保存"
- **THEN** 系统通过 `EntityService.Create` 创建一个 type=trigger 的 entity，自动设置 `target` 为当前视图对象（DAG 或 DAG-scoped node）

#### Scenario: 创建 node trigger 使用 DAG scope

- **WHEN** 用户在 DAG `default` 中选中 node `<node-id>` 并创建 trigger
- **THEN** 新 trigger entity 的 `target` SHALL 为 `node:default/<node-id>`

#### Scenario: 启用/禁用 trigger

- **WHEN** 用户在 trigger 列表中切换某 trigger 的 `enabled` 开关
- **THEN** 系统更新该 trigger entity 的 `enabled` 字段

#### Scenario: 删除 trigger

- **WHEN** 用户点击某 trigger 的"删除"按钮并确认
- **THEN** 系统通过 `EntityService.Delete` 删除该 trigger entity
