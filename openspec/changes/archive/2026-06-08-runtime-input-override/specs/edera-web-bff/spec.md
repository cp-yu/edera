## ADDED Requirements

### Requirement: DAG run 临时输入参数
edera-web BFF SHALL 在 `POST /api/dags/{name}/run` 接口中接受 `sourceSharedInputs`、`nodeInputs`、`appendNodes` 参数。

#### Scenario: 传递临时输入参数
- **WHEN** 客户端 POST `/api/dags/test/run` 并携带 `{sourceSharedInputs: {...}, nodeInputs: {...}, appendNodes: [...]}`
- **THEN** BFF SHALL 将这些参数通过 gRPC 传递给 edera-server

### Requirement: Retry 临时输入参数
edera-web BFF SHALL 在 `POST /api/dags/{name}/retry` 接口中接受 `sourceSharedInputs`、`nodeInputs`、`appendNodes` 参数。

#### Scenario: Retry 时传递临时输入
- **WHEN** 客户端 POST `/api/dags/test/retry` 并携带 `{node_ids: [...], sourceSharedInputs: {...}}`
- **THEN** BFF SHALL 将这些参数通过 gRPC 传递给 edera-server
