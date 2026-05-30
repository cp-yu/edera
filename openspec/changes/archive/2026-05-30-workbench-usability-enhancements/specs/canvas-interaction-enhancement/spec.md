## ADDED Requirements

### Requirement: Selected node neighborhood highlight
系统 SHALL 在用户点击 Canvas 上的节点时高亮该节点及其直接相连的一跳入边和出边。该高亮 SHALL 是渲染派生状态，不写入 DAG 配置。

#### Scenario: Highlight connected edges on node click
- **WHEN** 用户点击 Canvas 上的一个节点
- **THEN** 系统 SHALL 高亮该节点
- **AND** 系统 SHALL 高亮所有 `source` 或 `target` 等于该节点 ID 的 edge

#### Scenario: Do not highlight unrelated edges
- **WHEN** 用户点击 Canvas 上的一个节点
- **THEN** 系统 SHALL NOT 高亮与该节点不直接相连的 edge

#### Scenario: Selection highlight does not override runtime path color
- **WHEN** DAG 存在运行态 edge 高亮且用户选中一个节点
- **THEN** 系统 SHALL 保留运行态 edge 颜色
- **AND** 系统 SHALL 仅用额外 stroke width、opacity 或 shadow 表达手动选中态
