---
capabilities: []
---
## MODIFIED Requirements

### Requirement: 节点输入三步解析逻辑

系统 SHALL 按照三步顺序解析节点输入：Step 1 计算 base 输入，Step 2 检查临时输入，Step 3 应用输入模式。对于 source 节点，base 输入为 `node.config.default_entity`；当 source 节点既无 `sourceSharedInputs` 也无 `default_entity` 时，节点输入 SHALL 为空。

#### Scenario: Source 节点无临时输入使用默认配置

- **WHEN** source 节点没有临时输入
- **THEN** 节点输入为 `node.config.default_entity`

#### Scenario: Source 节点无临时输入且无默认配置

- **WHEN** source 节点既没有临时输入也没有 `default_entity`
- **THEN** 节点输入 SHALL 为空

#### Scenario: 非 source 节点无临时输入聚合前驱输出

- **WHEN** 非 source 节点没有临时输入
- **THEN** 节点输入为 `aggregate(edges)` 加上 `node.config.*`

#### Scenario: nodeInputs 覆盖模式

- **WHEN** `nodeInputs[node_id]` 存在且 `node_id` 不在 `appendNodes` 中
- **THEN** 节点输入完全替换为 `nodeInputs[node_id]`，忽略 base 输入

#### Scenario: nodeInputs 追加模式

- **WHEN** `nodeInputs[node_id]` 存在且 `node_id` 在 `appendNodes` 中
- **THEN** 节点输入为 `merge(base, nodeInputs[node_id])`

#### Scenario: sourceSharedInputs 仅对 source 节点生效

- **WHEN** source 节点没有 `nodeInputs` 但有 `sourceSharedInputs`
- **THEN** 节点输入为 `sourceSharedInputs`（覆盖模式）

#### Scenario: 非 source 节点忽略 sourceSharedInputs

- **WHEN** 非 source 节点存在 `sourceSharedInputs`
- **THEN** 节点输入不受 `sourceSharedInputs` 影响

#### Scenario: nodeInputs 优先于 sourceSharedInputs

- **WHEN** source 节点同时有 `nodeInputs[node_id]` 和 `sourceSharedInputs`
- **THEN** 使用 `nodeInputs[node_id]`，忽略 `sourceSharedInputs`
