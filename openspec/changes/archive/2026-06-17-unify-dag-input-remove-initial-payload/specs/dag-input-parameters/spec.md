## MODIFIED Requirements

### Requirement: 运行时参数传递
DAG 触发 API SHALL 通过 `sourceSharedInputs`、`nodeInputs`、`appendNodes` 三个参数表达运行时输入，不 SHALL 接受独立的入口 payload 参数。Source 节点的入口数据 SHALL 经 `sourceSharedInputs` 提供。

#### Scenario: CLI 传递 sourceSharedInputs
- **WHEN** 用户执行 `edera dag run my-dag --source-shared-inputs '{"entity": "entity://special"}'`
- **THEN** 系统 SHALL 将 `{entity: "entity://special"}` 作为所有 source 节点的输入

#### Scenario: CLI 传递 nodeInputs
- **WHEN** 用户执行 `edera dag run my-dag --node-inputs '{"node_1": "entity://custom"}'`
- **THEN** 系统 SHALL 将 `"entity://custom"` 作为 `node_1` 的输入

#### Scenario: HTTP API 传递临时输入
- **WHEN** 客户端 POST `/api/dags/my-dag/run` 并携带 `{"sourceSharedInputs": {...}, "nodeInputs": {...}, "appendNodes": [...]}`
- **THEN** 系统 SHALL 将临时输入参数传递给 DAG 运行时

#### Scenario: 无入口 payload 参数
- **WHEN** 客户端执行 DAG 运行且未提供 `sourceSharedInputs`
- **THEN** 系统 SHALL NOT 从请求体或其他字段推导入口 payload；source 节点输入由 `default_entity` 决定或为空

### Requirement: Sub-DAG 输入接口
当 DAG 作为 dag 节点嵌套执行时，父 DAG SHALL 通过 `input_mapping` 将上游输出映射到子 DAG 的 `sourceSharedInputs` 和 `nodeInputs`。子 DAG 的 source 节点输入 SHALL 仅来自该映射或子节点自身的 `default_entity`，不 SHALL 直接透传父节点的完整 payload。

#### Scenario: Sub-DAG input_mapping 映射到 sourceSharedInputs
- **WHEN** dag 节点的 `input_mapping` 为 `{symbol: "output.symbol"}`
- **THEN** 子 DAG 的 `sourceSharedInputs` 为 `{symbol: <mapped_value>}`

#### Scenario: Sub-DAG input_mapping 引用 entity
- **WHEN** dag 节点的 `input_mapping` 为 `"entity://scoring-mapping"`
- **THEN** 系统从 entity store 读取该 InputMapping entity，根据其 `shared` 和 `nodes` 字段生成子 DAG 的输入

#### Scenario: 无 input_mapping 的子 DAG source 节点
- **WHEN** dag 节点未声明 `input_mapping`，且子 DAG 的 source 节点未声明 `default_entity`
- **THEN** 该 source 节点输入 SHALL 为空，不 SHALL 接收父节点的 payload
