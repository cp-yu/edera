## ADDED Requirements

### Requirement: gRPC Client 实现
`rig` CLI SHALL 作为 gRPC client 连接 rig daemon，不再通过 HTTP 调用 FastAPI 后端。SHALL 自动读取 `~/.rig/` 中的证书和配置完成 mTLS 握手。

#### Scenario: gRPC 连接 daemon
- **WHEN** 用户执行任意 rig 命令
- **THEN** CLI SHALL 通过 gRPC 连接 daemon，使用 mTLS 认证

#### Scenario: 自动加载证书
- **WHEN** 用户执行 rig 命令
- **THEN** CLI SHALL 从 `~/.rig/client.crt` 和 `~/.rig/client.key` 加载证书

#### Scenario: 环境变量覆盖配置
- **WHEN** 环境变量 `RIG_CLIENT_CERT`、`RIG_CLIENT_KEY`、`RIG_DAEMON_ADDR` 已设置
- **THEN** CLI SHALL 优先使用环境变量中的配置，而非 `~/.rig/` 中的配置
