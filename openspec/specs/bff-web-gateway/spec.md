# bff-web-gateway Specification

## Purpose
此规约记录变更 core-architecture-overhaul 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: BFF 作为 gRPC Client
BFF SHALL 作为 gRPC client 连接 `edera-server`，持有自己的 client cert（CN=`bff:web-console`），代理 Web Console 的请求。BFF cert PEM 内容 SHALL 仅保留在 `edera-web` 进程内存，MUST NOT 落盘。

#### Scenario: BFF 启动时通过 bootstrap 拿 cert
- **WHEN** `edera-web` 启动
- **THEN** BFF SHALL 调用本机 `127.0.0.1:9091` 的 `SystemService.InitClient(common_name="bff:web-console")` 获取 client cert
- **AND** SHALL 用该 cert 构造 `GrpcClient` 连 `EDERA_SERVER_ADDR`

#### Scenario: BFF cert 不落盘
- **WHEN** BFF cert 签发完成
- **THEN** `edera-web` 进程 MUST NOT 创建 `~/.edera/bff/` 或任何持久化目录
- **AND** SHALL NOT 读取 `EDERA_BFF_DIR` 或 `RIG_BFF_DIR` 环境变量

### Requirement: HTTP REST API 兼容
BFF SHALL 保持现有 HTTP REST API 路由兼容，将 HTTP 请求转换为 gRPC 调用。

#### Scenario: HTTP 请求转 gRPC
- **WHEN** 浏览器 POST `/api/pipeline/dag/my-dag/run`
- **THEN** BFF SHALL 调用 `edera-server` 的 `DagService.Trigger` gRPC 方法

### Requirement: SSE 实时推送
BFF SHALL 提供 SSE endpoint，订阅 `edera-server` 的 event bus，实时推送 DAG 和 node 的状态变更到浏览器。

#### Scenario: SSE 推送 node 输出
- **WHEN** agent 节点输出一行文本到 stdout
- **THEN** BFF SHALL 通过 SSE 推送该行文本到订阅的浏览器

#### Scenario: SSE 推送 DAG 状态
- **WHEN** DAG 状态变更（started/completed/failed）
- **THEN** BFF SHALL 通过 SSE 推送状态变更事件到浏览器

### Requirement: Token 认证
BFF SHALL 支持 token 认证，浏览器请求 SHALL 携带 token（通过 Authorization header 或 cookie）。BFF 验证 token 后，使用自己的 client cert 转发请求到 `edera-server`。

#### Scenario: Token 验证成功
- **WHEN** 浏览器请求携带有效 token
- **THEN** BFF SHALL 验证 token，转发请求到 `edera-server`

#### Scenario: Token 验证失败
- **WHEN** 浏览器请求携带无效或缺失 token
- **THEN** BFF SHALL 返回 401 Unauthorized

### Requirement: Dev 模式免认证
BFF SHALL 支持 dev 模式（`EDERA_DEV=1`），在该模式下 SHALL 跳过 token 验证，允许无认证访问。

#### Scenario: Dev 模式跳过 token 验证
- **WHEN** BFF 运行在 `EDERA_DEV=1`，且浏览器请求未携带 token
- **THEN** BFF SHALL 允许请求，默认身份为 `human:dev`

### Requirement: 静态文件服务
BFF SHALL 提供 Web Console 的静态文件服务（HTML/JS/CSS）。

#### Scenario: 服务静态文件
- **WHEN** 浏览器访问 `/`
- **THEN** BFF SHALL 返回 Web Console 的 index.html

