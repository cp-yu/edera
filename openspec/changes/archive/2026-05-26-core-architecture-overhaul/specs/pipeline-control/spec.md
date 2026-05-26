## ADDED Requirements

### Requirement: DAG 运行 API 增加 inputs 参数
系统 SHALL 在 DAG 触发 API 中支持 `inputs` 参数，允许外部传入 DAG 声明的输入参数。

#### Scenario: API 传递 inputs
- **WHEN** 客户端 POST `/api/pipeline/dag/my-dag/run` 并携带 `{"inputs": {"ticker": "00100.HK"}}`
- **THEN** 系统 SHALL 将 inputs 传递给 DAG 运行时，绑定的 source 节点使用传入值

#### Scenario: 无 inputs 参数时正常运行
- **WHEN** 客户端 POST `/api/pipeline/dag/my-dag/run` 不携带 `inputs` 参数
- **THEN** 系统 SHALL 正常启动 DAG，source 节点从 `source_names` 拉取数据
