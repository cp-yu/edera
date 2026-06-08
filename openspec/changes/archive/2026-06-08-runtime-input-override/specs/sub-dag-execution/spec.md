## MODIFIED Requirements

### Requirement: Dag 节点类型支持
系统 SHALL 支持 `type: dag` 的节点，该节点引用另一个 DAG 作为子图执行。Dag 节点 SHALL 包含 `dag_ref` 字段（目标 DAG 名称）和 `input_mapping` 字段（输入参数映射）。`input_mapping` SHALL 支持 `dict[str, str]` 或 `str` 类型。

#### Scenario: Dag 节点配置加载
- **WHEN** 节点配置 `type: dag` 且 `dag_ref: target-dag`
- **THEN** 系统 SHALL 将该节点识别为子 DAG 节点

#### Scenario: input_mapping 为 dict 类型
- **WHEN** dag 节点的 `input_mapping` 为 `{symbol: "output.symbol", date: "output.date"}`
- **THEN** 系统 SHALL 使用该 dict 映射父节点输出到子 DAG 的 `sourceSharedInputs`

#### Scenario: input_mapping 为 entity 引用
- **WHEN** dag 节点的 `input_mapping` 为 `"entity://scoring-mapping"`
- **THEN** 系统 SHALL 从 entity store 读取该 InputMapping entity，使用其 `shared`、`nodes`、`append_nodes` 字段生成子 DAG 的输入参数
