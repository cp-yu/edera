## MODIFIED Requirements

### Requirement: edera-web 纯 BFF 角色
`edera-web` SHALL 作为纯 BFF（Backend for Frontend）运行，进程内 MUST NOT 实例化 `DagController`，所有数据操作 MUST 通过 gRPC 调用 `edera-server`。`PipelineController` 类名已废弃，改为 `DagController`。

#### Scenario: create_app 单一签名
- **WHEN** 检查 `web/app.py` 的 `create_app` 函数签名
- **THEN** 函数 SHALL 仅接受 `grpc_client` 参数，MUST NOT 接受 `controller` 或 `config_dir`、`handler_registry` 参数

#### Scenario: 不实例化 controller
- **WHEN** `edera-web` 启动
- **THEN** 进程 MUST NOT 实例化 `DagController`，MUST NOT 调用 `load_app_config`

#### Scenario: 必须依赖 edera-server
- **WHEN** `edera-web` 启动但 `EDERA_SERVER_ADDR` 未设置
- **THEN** 进程 SHALL 输出错误 "EDERA_SERVER_ADDR not set" 并以非零状态退出

## ADDED Requirements

### Requirement: gRPC client 适配新 service
`edera-web` 的 gRPC client SHALL 适配重组后的 service 结构，使用 `DagService`、`EventService`、`SystemService` 替代 `PipelineService`。

#### Scenario: 调用 DagService.Run
- **WHEN** 前端请求运行 DAG
- **THEN** BFF SHALL 调用 `DagService.Run` 并返回 `DagRunRef{run_id: "..."}`

#### Scenario: 调用 EventService.Emit
- **WHEN** 前端请求注入事件
- **THEN** BFF SHALL 调用 `EventService.Emit`

#### Scenario: 调用 SystemService scheduler 控制
- **WHEN** 前端请求暂停或恢复 scheduler
- **THEN** BFF SHALL 调用 `SystemService.PauseScheduler` 或 `SystemService.ResumeScheduler`

### Requirement: HTTP API 路径保持稳定
BFF 的 HTTP API 路径 SHALL 保持稳定，前端无需修改路由。内部 gRPC 调用的变更对前端透明。

#### Scenario: DAG 运行 API 路径
- **WHEN** 前端 POST `/api/dags/{name}/run`
- **THEN** BFF SHALL 调用 `DagService.Run` 并返回 `{run_id: "..."}`

#### Scenario: 事件注入 API 路径
- **WHEN** 前端 POST `/api/events/emit`
- **THEN** BFF SHALL 调用 `EventService.Emit`

### Requirement: 响应中使用 run_id
BFF 返回给前端的 JSON 响应 SHALL 使用 `run_id` 字段，不再使用 `cycle_id`。

#### Scenario: DAG 状态响应
- **WHEN** 前端 GET `/api/dags/{name}/status`
- **THEN** BFF SHALL 返回 `{current_run_id: "...", status: "running", ...}`

#### Scenario: 节点历史响应
- **WHEN** 前端 GET `/api/nodes/{id}/history`
- **THEN** BFF SHALL 返回 `[{run_id: "...", status: "succeeded", ...}, ...]`
