## REMOVED Requirements

### Requirement: DAG 输入参数声明
**Reason**: DAG 输入参数机制被运行时临时输入机制替代
**Migration**: 使用运行时 `sourceSharedInputs` 和 `nodeInputs` 参数替代 DAG.inputs

### Requirement: Source 节点 Input Binding
**Reason**: input_binding 机制被移除，改用运行时临时输入
**Migration**: 将 `input_binding` 字段的值移到节点配置的 `config.default_entity`；运行时使用 `sourceSharedInputs` 或 `nodeInputs` 覆盖

### Requirement: Web Console 输入表单
**Reason**: 输入机制改为运行时临时输入，不再基于 DAG.inputs 声明
**Migration**: 使用新的临时输入弹窗 UI，支持 `sourceSharedInputs`、`nodeInputs`、`appendNodes` 配置

## MODIFIED Requirements

### Requirement: 运行时参数传递
DAG 触发 API SHALL 支持 `sourceSharedInputs`、`nodeInputs`、`appendNodes` 参数，允许运行时临时覆盖或追加节点输入。

#### Scenario: CLI 传递 sourceSharedInputs
- **WHEN** 用户执行 `edera dag run my-dag --source-shared-inputs '{"entity": "entity://special"}'`
- **THEN** 系统 SHALL 将 `{entity: "entity://special"}` 作为所有 source 节点的输入

#### Scenario: CLI 传递 nodeInputs
- **WHEN** 用户执行 `edera dag run my-dag --node-inputs '{"node_1": "entity://custom"}'`
- **THEN** 系统 SHALL 将 `"entity://custom"` 作为 `node_1` 的输入

#### Scenario: HTTP API 传递临时输入
- **WHEN** 客户端 POST `/api/dags/my-dag/run` 并携带 `{"sourceSharedInputs": {...}, "nodeInputs": {...}, "appendNodes": [...]}`
- **THEN** 系统 SHALL 将临时输入参数传递给 DAG 运行时

### Requirement: Sub-DAG 输入接口
当 DAG 作为 dag 节点嵌套执行时，父 DAG SHALL 通过 `input_mapping` 将上游输出映射到子 DAG 的 `sourceSharedInputs` 和 `nodeInputs`。

#### Scenario: Sub-DAG input_mapping 映射到 sourceSharedInputs
- **WHEN** dag 节点的 `input_mapping` 为 `{symbol: "output.symbol"}`
- **THEN** 子 DAG 的 `sourceSharedInputs` 为 `{symbol: <mapped_value>}`

#### Scenario: Sub-DAG input_mapping 引用 entity
- **WHEN** dag 节点的 `input_mapping` 为 `"entity://scoring-mapping"`
- **THEN** 系统从 entity store 读取该 InputMapping entity，根据其 `shared` 和 `nodes` 字段生成子 DAG 的输入
