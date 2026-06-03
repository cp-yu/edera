---
capabilities:
  - cap.web.dag-run-observability
---
# dag-run-observability Specification

## Purpose
此规约记录变更 dag-observability-controllability 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Inspector Runtime tab

系统 SHALL 在 Inspector 面板增加 Runtime tab，展示选中节点的当前运行状态和 output entities。

#### Scenario: 展示节点运行状态

- **WHEN** 用户选中节点且切换到 Runtime tab
- **THEN** 系统 SHALL 展示该节点在当前/最近 run 中的 status、started_at、ended_at、error 信息

#### Scenario: 展示节点 output entities

- **WHEN** 用户在 Runtime tab 查看已完成节点
- **THEN** 系统 SHALL 展示该节点在当前 run 中产出的所有 `NodeOutputEntity` 列表

#### Scenario: 右键快捷切换到 Runtime tab

- **WHEN** 用户右键节点选择"查看当前运行状态"
- **THEN** 系统 MUST 选中该节点并将 Inspector 切换到 Runtime tab

### Requirement: Edge 数据流查看

系统 SHALL 在用户点击 edge 时将 Inspector 切换为 edge 详情模式，展示上游节点产出的 entities。

#### Scenario: 点击 edge 展示上游 entities

- **WHEN** 用户点击 edge（node-A → node-B）
- **THEN** Inspector MUST 切换为 edge 详情模式，展示 `NodeOutputEntity WHERE node_id = node-A AND run_id = current` 的结果列表

#### Scenario: Edge 详情包含历史跳转

- **WHEN** Inspector 处于 edge 详情模式
- **THEN** 系统 SHALL 提供"查看历史"链接，跳转到上游节点的历史页面

### Requirement: 节点历史页面

系统 SHALL 提供独立 route `/history/dag/{dag_name}/nodes/{node_id}`，展示节点在所有历史 run 中的运行记录。

#### Scenario: 展示运行记录列表

- **WHEN** 用户访问 `/history/dag/{dag_name}/nodes/{node_id}`
- **THEN** 系统 SHALL 展示该节点的所有 `NodeRun` 记录，按 `started_at` 降序排列，每条包含 run_id、status、started_at、ended_at、error

#### Scenario: 展开查看 output entities

- **WHEN** 用户在历史页面点击某条运行记录
- **THEN** 系统 SHALL 展示该 run 中该节点产出的 `NodeOutputEntity` 列表

#### Scenario: Retry 链标识

- **WHEN** 历史记录中存在 retry run（source="retry"）
- **THEN** 系统 SHALL 标识该记录为 retry 并展示 `retry_of` 关联的原始 run_id

### Requirement: 右键菜单扩展

系统 SHALL 扩展节点右键菜单，增加能观性和能控性选项。菜单 MUST 为扁平结构。

#### Scenario: 节点右键菜单完整选项

- **WHEN** 用户右键节点
- **THEN** 系统 SHALL 展示以下菜单项（扁平排列）：查看当前运行状态、查看历史、重试节点、重试节点及下游、分隔线、删除节点、断开所有连接

#### Scenario: Edge 右键菜单包含历史

- **WHEN** 用户右键 edge
- **THEN** 系统 SHALL 在现有菜单项基础上增加"查看上游节点历史"选项，点击后跳转到上游节点的历史页面

