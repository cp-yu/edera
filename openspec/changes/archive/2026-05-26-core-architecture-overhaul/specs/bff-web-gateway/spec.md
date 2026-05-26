## ADDED Requirements

### Requirement: BFF 作为 gRPC Client
BFF SHALL 作为 gRPC client 连接 rig daemon，持有自己的 client cert（CN=`bff:web-console`），代理 Web Console 的请求。

#### Scenario: BFF 连接 daemon
- **WHEN** BFF 启动
- **THEN** BFF SHALL 使用 client cert 连接 daemon 的 gRPC 服务

### Requirement: HTTP REST API 兼容
BFF SHALL 保持现有 HTTP REST API 路由兼容，将 HTTP 请求转换为 gRPC 调用。

#### Scenario: HTTP 请求转 gRPC
- **WHEN** 浏览器 POST `/api/pipeline/dag/my-dag/run`
- **THEN** BFF SHALL 调用 daemon 的 `DagService.Trigger` gRPC 方法

### Requirement: SSE 实时推送
BFF SHALL 提供 SSE endpoint，订阅 daemon 的 event bus，实时推送 DAG 和 node 的状态变更到浏览器。

#### Scenario: SSE 推送 node 输出
- **WHEN** agent 节点输出一行文本到 stdout
- **THEN** BFF SHALL 通过 SSE 推送该行文本到订阅的浏览器

#### Scenario: SSE 推送 DAG 状态
- **WHEN** DAG 状态变更（started/completed/failed）
- **THEN** BFF SHALL 通过 SSE 推送状态变更事件到浏览器

### Requirement: Token 认证
BFF SHALL 支持 token 认证，浏览器请求 SHALL 携带 token（通过 Authorization header 或 cookie）。BFF 验证 token 后，使用自己的 client cert 转发请求到 daemon。

#### Scenario: Token 验证成功
- **WHEN** 浏览器请求携带有效 token
- **THEN** BFF SHALL 验证 token，转发请求到 daemon

#### Scenario: Token 验证失败
- **WHEN** 浏览器请求携带无效或缺失 token
- **THEN** BFF SHALL 返回 401 Unauthorized

### Requirement: Dev 模式免认证
BFF SHALL 支持 dev 模式（`RIG_ENV=dev`），在该模式下 SHALL 跳过 token 验证，允许无认证访问。

#### Scenario: Dev 模式跳过 token 验证
- **WHEN** BFF 运行在 dev 模式，且浏览器请求未携带 token
- **THEN** BFF SHALL 允许请求，默认身份为 `human:dev`

### Requirement: 静态文件服务
BFF SHALL 提供 Web Console 的静态文件服务（HTML/JS/CSS）。

#### Scenario: 服务静态文件
- **WHEN** 浏览器访问 `/`
- **THEN** BFF SHALL 返回 Web Console 的 index.html
