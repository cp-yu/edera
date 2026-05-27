# rig-daemon-grpc Specification

## Purpose
此规约记录变更 core-architecture-overhaul 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: gRPC Service 定义
Rig daemon SHALL 暴露 gRPC 服务，包含 EntityService、DagService、NodeService、SystemService 四个 service。Proto 定义 SHALL 兼容 Rust tonic。

#### Scenario: EntityService 提供 CRUD
- **WHEN** 客户端调用 EntityService.Create
- **THEN** daemon SHALL 创建 entity 并返回创建结果

#### Scenario: DagService 提供触发和查询
- **WHEN** 客户端调用 DagService.Trigger
- **THEN** daemon SHALL 启动 DAG 执行并返回 cycle_id

### Requirement: mTLS 传输安全
Daemon SHALL 使用 mTLS 进行传输加密和客户端身份认证。Daemon SHALL 持有 server cert，客户端 SHALL 持有 client cert。

#### Scenario: 客户端证书验证
- **WHEN** 客户端连接 daemon 但未提供有效 client cert
- **THEN** daemon SHALL 拒绝连接

#### Scenario: 从证书 CN 提取身份
- **WHEN** 客户端连接成功，cert CN 为 `node:llm-analyzer`
- **THEN** daemon SHALL 提取身份为 `node:llm-analyzer`，用于权限判断

### Requirement: Agent 短期证书签发
Daemon 启动 agent 节点前，SHALL 使用内部 CA 签发短期 client cert，CN 为 `node:{instance_id}`，TTL 对齐节点 timeout。签发后 SHALL 将 PEM 内容保持在内存中，通过环境变量注入 subprocess，不写入文件系统。

#### Scenario: Agent 节点证书签发
- **WHEN** daemon 启动 agent 节点 `llm-analyzer`
- **THEN** daemon SHALL 签发 client cert，CN=`node:llm-analyzer`，TTL=节点 timeout

#### Scenario: 证书通过环境变量注入 PEM 内容
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `RIG_CLIENT_CERT` SHALL 包含签发的 client cert PEM 文本内容（非文件路径）

#### Scenario: 私钥通过环境变量注入 PEM 内容
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `RIG_CLIENT_KEY` SHALL 包含签发的 client key PEM 文本内容（非文件路径）

#### Scenario: CA cert 通过环境变量注入 PEM 内容
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `RIG_CA_CERT` SHALL 包含 daemon CA cert PEM 文本内容

#### Scenario: 证书不落盘
- **WHEN** daemon 完成 agent cert 签发
- **THEN** daemon SHALL 不将 cert 或 key 写入文件系统

#### Scenario: Resume 重新签发
- **WHEN** 用户调用 resume API 恢复已停止的 agent 节点
- **THEN** daemon SHALL 重新签发新的短期 cert（新 TTL），不复用旧 cert

### Requirement: Dev 模式
Daemon SHALL 支持 dev 模式（`RIG_ENV=dev`），在该模式下 SHALL 放宽安全限制，支持本地开发场景（如 WSL→Windows）。

#### Scenario: Dev 模式允许无证书连接
- **WHEN** daemon 运行在 dev 模式，且客户端连接未提供 client cert
- **THEN** daemon SHALL 允许连接，身份默认为 `human:dev`

### Requirement: 权限判断
Daemon SHALL 根据客户端身份（从 cert CN 提取）查找对应的 `entity_permissions`，执行权限校验。

#### Scenario: Agent 节点权限校验
- **WHEN** 客户端身份为 `node:llm-analyzer`，调用 EntityService.Update
- **THEN** daemon SHALL 查找该节点的 `entity_permissions`，校验是否允许写入目标字段

