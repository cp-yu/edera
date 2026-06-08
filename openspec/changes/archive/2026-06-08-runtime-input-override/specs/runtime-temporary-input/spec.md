## ADDED Requirements

### Requirement: 节点输入三步解析逻辑

系统 SHALL 按照三步顺序解析节点输入：Step 1 计算 base 输入，Step 2 检查临时输入，Step 3 应用输入模式。

#### Scenario: Source 节点无临时输入使用默认配置

- **WHEN** source 节点没有临时输入
- **THEN** 节点输入为 `node.config.default_entity`

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

### Requirement: 浅合并语义

追加模式的 `merge(base, override)` SHALL 执行浅合并。如果两者都是 dict，返回 `{...base, ...override}`。否则返回 `override`。

#### Scenario: Dict 浅合并

- **WHEN** `base = {a: 1, b: 2}` 且 `override = {b: 3, c: 4}`
- **THEN** merge 结果为 `{a: 1, b: 3, c: 4}`

#### Scenario: 非 dict 直接覆盖

- **WHEN** `base = "entity://old"` 且 `override = "entity://new"`
- **THEN** merge 结果为 `"entity://new"`

### Requirement: DAG run API 临时输入参数

`POST /api/dags/{name}/run` SHALL 接受 `sourceSharedInputs`、`nodeInputs`、`appendNodes` 三个可选参数。

#### Scenario: 运行 DAG 时指定 sourceSharedInputs

- **WHEN** 调用 `/api/dags/news-workflow/run` 传入 `{sourceSharedInputs: {entity: "entity://special"}}`
- **THEN** 所有 source 节点使用 `{entity: "entity://special"}` 作为输入

#### Scenario: 运行 DAG 时指定 nodeInputs

- **WHEN** 调用 `/api/dags/analysis/run` 传入 `{nodeInputs: {node_1: "entity://custom"}}`
- **THEN** `node_1` 使用 `"entity://custom"` 作为输入

#### Scenario: 运行 DAG 时指定 appendNodes

- **WHEN** 调用 `/api/dags/test/run` 传入 `{nodeInputs: {processor: {debug: true}}, appendNodes: ["processor"]}`
- **THEN** `processor` 节点输入为 base 加上 `{debug: true}`

### Requirement: Retry API 临时输入参数

`POST /api/dags/{name}/retry` SHALL 接受 `sourceSharedInputs`、`nodeInputs`、`appendNodes` 三个可选参数。

#### Scenario: Retry 时覆盖节点输入

- **WHEN** 调用 `/api/dags/pipeline/retry` 传入 `{node_ids: ["node_1"], nodeInputs: {node_1: "entity://fix"}}`
- **THEN** `node_1` 重试时使用 `"entity://fix"` 作为输入

#### Scenario: Retry 时追加测试参数

- **WHEN** 调用 `/api/dags/pipeline/retry` 传入 `{node_ids: ["analyzer"], nodeInputs: {analyzer: {test_mode: true}}, appendNodes: ["analyzer"]}`
- **THEN** `analyzer` 重试时输入为原始输入加上 `{test_mode: true}`

### Requirement: Node trigger 支持追加模式

`run_node_trigger(target, payload, append)` SHALL 支持 `append` 参数。当 `append=True` 时，将 `node_id` 加入 `appendNodes`。

#### Scenario: Node trigger 覆盖模式

- **WHEN** 调用 `run_node_trigger("dag/node_1", "entity://special", append=False)`
- **THEN** `node_1` 输入完全替换为 `"entity://special"`

#### Scenario: Node trigger 追加模式

- **WHEN** 调用 `run_node_trigger("dag/node_1", {extra: "value"}, append=True)`
- **THEN** `node_1` 输入为 base 加上 `{extra: "value"}`

### Requirement: 错误提示

系统 SHALL 在检测到已废弃字段时给出清晰的错误提示和迁移建议。

#### Scenario: 检测到 input_binding

- **WHEN** 节点配置包含 `input_binding` 字段
- **THEN** 系统抛出错误，提示 "`input_binding` 已废弃，请将其移到 `config.default_entity`"

#### Scenario: 检测到 DAG.inputs

- **WHEN** DAG 配置包含 `inputs` 字段
- **THEN** 系统抛出错误，提示 "`DAG.inputs` 已废弃，请使用运行时 `sourceSharedInputs` 和 `nodeInputs`"
