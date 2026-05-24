## ADDED Requirements

### Requirement: 前端连线环检测

系统 SHALL 在用户创建新边时执行环检测，如果新边会导致 DAG 形成环则 MUST 拒绝创建并警告用户。

#### Scenario: 检测到环时拒绝连线

- **WHEN** 用户在画布上从 node-B 拖线到 node-A，且 node-A → node-B 路径已存在
- **THEN** 系统 MUST 拒绝创建该边，显示 toast 警告"连线会形成环，已拒绝"

#### Scenario: 无环时正常创建连线

- **WHEN** 用户创建的新边不会导致环
- **THEN** 系统 SHALL 正常创建该边，无警告

#### Scenario: 环检测算法

- **WHEN** `onConnect` 回调触发
- **THEN** 系统 MUST 从 target 节点出发沿现有 edges 做 DFS，检查是否能到达 source 节点。如果能到达则存在环
