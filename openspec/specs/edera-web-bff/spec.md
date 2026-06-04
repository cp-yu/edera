---
capabilities:
  - cap.web.edera-web-bff
---
# edera-web-bff Specification

## Purpose
定义 `edera-web` 网页 BFF 的纯 gRPC client 角色、启动配置、BFF cert 内存模式、HTTP/SSE 网关、token 认证、静态文件服务和服务端部署拓扑。
## Requirements
### Requirement: edera-web 纯 BFF 角色
`edera-web` SHALL 作为纯 BFF（Backend for Frontend）运行，进程内 MUST NOT 实例化 `DagController`，所有数据操作 MUST 通过 gRPC 调用 `edera-server`。

#### Scenario: create_app 单一签名
- **WHEN** 检查 `web/app.py` 的 `create_app` 函数签名
- **THEN** 函数 SHALL 仅接受 `grpc_client` 参数，MUST NOT 接受 `controller` 或 `config_dir`、`handler_registry` 参数

#### Scenario: 不实例化 controller
- **WHEN** `edera-web` 启动
- **THEN** 进程 MUST NOT 实例化 `DagController`，MUST NOT 调用 `load_app_config`

#### Scenario: 必须依赖 edera-server
- **WHEN** `edera-web` 启动但 `EDERA_SERVER_ADDR` 未设置
- **THEN** 进程 SHALL 输出错误 "EDERA_SERVER_ADDR not set" 并以非零状态退出

### Requirement: 配置无知契约
`edera-web` 进程 SHALL NOT 读取 `config/` 目录或 `system.toml`。所有面向前端的 entity types、DAG 定义等元数据 MUST 通过 gRPC 拉取。

#### Scenario: 不读 config 目录
- **WHEN** `edera-web` 启动
- **THEN** 进程 MUST NOT 调用 `load_app_config`，MUST NOT 读取 `config/system.toml` 中的 `web_host`/`web_port`

#### Scenario: Entity types 通过 gRPC 拉
- **WHEN** 浏览器通过 BFF 请求 entity types 列表
- **THEN** BFF SHALL 通过 `EntityService.List(type="entity_type")` 调用 `edera-server`，不在本地缓存配置目录内容

### Requirement: BFF cert 内存模式
`edera-web` 启动时 SHALL 从服务端本机 `EDERA_DATA_DIR/bootstrap.json` 读取实际 bootstrap endpoint，并调用该本机端口的 `SystemService.InitClient(common_name="bff:web-console")` 拿 client cert。PEM 内容仅保留在进程内存，MUST NOT 写入文件系统。

#### Scenario: 启动时拿 cert
- **WHEN** `edera-web` 启动且不处于 `EDERA_DEV=1`
- **THEN** 进程 SHALL 读取 `EDERA_DATA_DIR/bootstrap.json` 中的 `host` 和 `port`
- **AND** SHALL 调用该 endpoint 的 `SystemService.InitClient`，得到 BFF client cert/key/ca PEM
- **AND** SHALL 用该 cert 构造 `GrpcClient` 连 `EDERA_SERVER_ADDR`

#### Scenario: bootstrap 状态缺失
- **WHEN** `edera-web` 启动且 `bootstrap.json` 不存在、格式无效或缺少端口
- **THEN** 进程 SHALL 失败退出并报告 bootstrap 状态不可用

#### Scenario: cert 不落盘
- **WHEN** BFF cert 签发完成
- **THEN** 进程 MUST NOT 创建 `~/.edera/bff/` 或任何持久化目录
- **AND** SHALL NOT 设置任何 BFF cert 持久化目录环境变量

#### Scenario: 重启自愈
- **WHEN** `edera-web` 进程因任意原因重启
- **THEN** 进程 SHALL 重新读取 `bootstrap.json` 并调用 bootstrap 拿新 cert，不依赖任何持久化 cert 状态

### Requirement: --bind 与 --port 配置
`edera-web` 启动时 SHALL 接受 `--bind`/`--port` flag，未传时回退到 `EDERA_WEB_BIND`/`EDERA_WEB_PORT` 环境变量，再无则使用默认值 `127.0.0.1:8000`。

#### Scenario: 默认监听
- **WHEN** `edera-web` 启动且既未传 flag 也未设 env
- **THEN** 进程 SHALL 监听 `127.0.0.1:8000`

#### Scenario: flag 优先
- **WHEN** 用户启动 `edera-web --bind 0.0.0.0 --port 8080`，且 `EDERA_WEB_BIND=192.168.1.10` 已设置
- **THEN** 进程 SHALL 监听 `0.0.0.0:8080`，忽略环境变量

#### Scenario: env fallback
- **WHEN** 用户启动 `edera-web` 不带 flag，但 `EDERA_WEB_BIND=0.0.0.0` 与 `EDERA_WEB_PORT=8080` 已设置
- **THEN** 进程 SHALL 监听 `0.0.0.0:8080`

### Requirement: 客户端 / 服务端拓扑
`edera-web` SHALL 与 `edera-server` 部署在同一台服务端主机；浏览器从客户端连接 `edera-web` HTTP 端口；CLI 在客户端机器直接连 `edera-server` gRPC 端口。

#### Scenario: 同机部署
- **WHEN** 部署 Edera 服务端
- **THEN** `edera-server` 与 `edera-web` SHALL 跑在同一主机
- **AND** `edera-web` SHALL 通过服务端本机 `bootstrap.json` 指向的 `127.0.0.1:{port}` bootstrap 端口拿 cert
- **AND** `edera-web` SHALL 通过 `EDERA_SERVER_ADDR`（通常 `127.0.0.1:9090`）连 `edera-server` 主端口

#### Scenario: bootstrap.json 不是远程协议
- **WHEN** 远程客户端需要执行 `edera client init`
- **THEN** `edera-web` 的 `bootstrap.json` discovery 机制 SHALL NOT 被用作远程自动发现协议

### Requirement: BFF route handler 纯 gRPC 调用
`edera-web` 的所有 HTTP route handler MUST 通过 `GrpcClient` 调用 `edera-server`，MUST NOT 调用本地配置加载器、本地存储 repository 或本地 DagController。

#### Scenario: Graph 编辑 route 通过 gRPC
- **WHEN** 浏览器请求 `GET /api/graph/dag/{name}`
- **THEN** BFF SHALL 通过 `GrpcClient.graph_get_dag(name)` 调用 GraphService，将返回的 JSON 直接透传

#### Scenario: Config 读写 route 通过 gRPC
- **WHEN** 浏览器请求 `PUT /api/config/system` 携带 TOML 内容
- **THEN** BFF SHALL 通过 `GrpcClient.config_save_system(content)` 调用 ConfigService，将返回结果透传

#### Scenario: Query route 通过 gRPC
- **WHEN** 浏览器请求 `GET /api/results`
- **THEN** BFF SHALL 通过 `GrpcClient.query_results_summary(...)` 调用 QueryService，将返回结果透传

#### Scenario: DAG 控制 route 通过 gRPC
- **WHEN** 浏览器请求 `POST /api/dags/{name}/retry`
- **THEN** BFF SHALL 通过 `GrpcClient.dag_retry(...)` 调用 DagService，将返回结果透传

### Requirement: BFF 不再 import 业务模块
`edera-web` 的 route handler 模块 MUST NOT import `edera_core.config.*`、`edera_core.storage.*`、`edera_core.dag_controller` 中的任何符号。

#### Scenario: routes.py 不 import config 模块
- **WHEN** 检查 `packages/core/src/edera_core/web/routes.py` 的 import 列表
- **THEN** 文件 MUST NOT import `edera_core.config.editor`、`edera_core.config.entities`、`edera_core.config.loader`、`edera_core.config.schema`

#### Scenario: routes.py 不 import storage 模块
- **WHEN** 检查 `packages/core/src/edera_core/web/routes.py` 的 import 列表
- **THEN** 文件 MUST NOT import `edera_core.storage.repository`

#### Scenario: routes.py 不 import DAG controller 模块
- **WHEN** 检查 `packages/core/src/edera_core/web/routes.py` 的 import 列表
- **THEN** 文件 MUST NOT import `edera_core.dag_controller`

### Requirement: BFF deps.py 仅暴露 gRPC client
`edera-web` 的 `deps.py` MUST 只提供 `grpc_client()` 和 `error_response()` 两个 helper，MUST NOT 包含 `controller()`、`config_dir()`、`handler_registry()` 等本地资源访问函数。

#### Scenario: deps.py 函数集合
- **WHEN** 检查 `packages/core/src/edera_core/web/deps.py`
- **THEN** 文件 SHALL 仅 export `grpc_client` 和 `error_response`
- **AND** MUST NOT 定义 `controller`、`config_dir`、`handler_registry` 函数

#### Scenario: 无 501 fail-closed stub
- **WHEN** 检查 deps.py 函数实现
- **THEN** 文件 MUST NOT 包含返回 HTTP 501 的占位函数

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
BFF 返回给前端的 JSON 响应 SHALL 使用 `run_id` 字段。

#### Scenario: DAG 状态响应
- **WHEN** 前端 GET `/api/dags/{name}/status`
- **THEN** BFF SHALL 返回 `{current_run_id: "...", status: "running", ...}`

#### Scenario: 节点历史响应
- **WHEN** 前端 GET `/api/nodes/{id}/history`
- **THEN** BFF SHALL 返回 `[{run_id: "...", status: "succeeded", ...}, ...]`

### Requirement: No hard-coded default DAG routes
`edera-web` SHALL expose DAG run, stop, status and history behavior through parameterized DAG routes. It MUST NOT provide hard-coded `default` DAG compatibility routes that bypass the `{dag_name}` path parameter.

#### Scenario: Run default through parameterized route
- **WHEN** client needs to run DAG `default`
- **THEN** client SHALL call `POST /api/dags/default/run`
- **AND** the route SHALL be handled by the generic `/api/dags/{dag_name}/run` handler

#### Scenario: No duplicate default run route
- **WHEN** web routes are registered
- **THEN** there MUST NOT be a separate route handler dedicated to `/api/dags/default/run`

#### Scenario: No default-only node history route
- **WHEN** client queries node history
- **THEN** client SHALL use a route that includes the DAG name
- **AND** web routes MUST NOT hard-code `dag_name = "default"` for history queries

### Requirement: BFF SSE 实时推送
`edera-web` SHALL 提供 SSE endpoint，订阅 `edera-server` 的 event bus，实时推送 DAG 状态、node 状态和 agent stdout 到浏览器。

#### Scenario: BFF SSE 推送 node 输出
- **WHEN** agent 节点输出一行文本到 stdout
- **THEN** BFF SHALL 通过 SSE 推送该行文本到订阅的浏览器

#### Scenario: SSE 推送 DAG 状态
- **WHEN** DAG 状态变更（started/completed/failed）
- **THEN** BFF SHALL 通过 SSE 推送状态变更事件到浏览器

### Requirement: BFF token 认证
`edera-web` SHALL 支持 token 认证，浏览器请求 SHALL 携带 token（通过 Authorization header 或 cookie）。BFF 验证 token 后，使用自己的 client cert 转发请求到 `edera-server`。

#### Scenario: Token 验证成功
- **WHEN** 浏览器请求携带有效 token
- **THEN** BFF SHALL 验证 token，转发请求到 `edera-server`

#### Scenario: Token 验证失败
- **WHEN** 浏览器请求携带无效或缺失 token
- **THEN** BFF SHALL 返回 401 Unauthorized

#### Scenario: Dev 模式跳过 token 验证
- **WHEN** BFF 运行在 `EDERA_DEV=1`，且浏览器请求未携带 token
- **THEN** BFF SHALL 允许请求，默认身份为 `human:dev`

### Requirement: Web Console 静态文件服务
`edera-web` SHALL 提供 Web Console 的静态文件服务（HTML/JS/CSS）。

#### Scenario: 服务静态文件
- **WHEN** 浏览器访问 `/`
- **THEN** BFF SHALL 返回 Web Console 的 index.html

### Requirement: BFF node execution logs API
`edera-web` SHALL 通过纯 gRPC client 暴露节点 execution logs 查询 HTTP API。该 API MUST 支持按 `run_id` 和 `node_id` 过滤，并 MUST NOT 读取本地 repository、config 目录或 `DagController`。

#### Scenario: HTTP logs route uses gRPC
- **WHEN** 浏览器请求节点 execution logs HTTP route
- **THEN** BFF SHALL 通过 `GrpcClient` 调用 `edera-server` 的查询 RPC
- **AND** BFF SHALL 将返回 JSON 透传给浏览器

#### Scenario: Logs query filters by run and node
- **WHEN** 浏览器请求某个 `run_id` 与 `node_id` 的 execution logs
- **THEN** BFF SHALL 将 `run_id` 和 `node_id` 传递给 gRPC 查询
- **AND** 响应 SHALL 只包含该节点在该 run 下的日志索引或日志内容

#### Scenario: Node outputs route remains output-only
- **WHEN** 浏览器请求 `/api/node-outputs`
- **THEN** BFF SHALL 继续只返回业务 output entities
- **AND** BFF MUST NOT 将 execution logs 混入 output entities 响应

