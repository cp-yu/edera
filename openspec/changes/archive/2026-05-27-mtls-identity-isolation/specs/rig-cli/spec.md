## MODIFIED Requirements

### Requirement: gRPC Client 实现
`rig` CLI SHALL 作为 gRPC client 连接 rig daemon。证书加载优先级：环境变量 PEM 内容 > `~/.rig/` 文件 fallback。

#### Scenario: gRPC 连接 daemon
- **WHEN** 用户执行任意 rig 命令
- **THEN** CLI SHALL 通过 gRPC 连接 daemon，使用 mTLS 认证

#### Scenario: 环境变量 PEM 内容优先
- **WHEN** 环境变量 `RIG_CLIENT_CERT` 已设置（值为 PEM 文本内容）
- **THEN** CLI SHALL 直接使用该 PEM 内容作为 client cert，不读取文件系统

#### Scenario: 文件 fallback
- **WHEN** 环境变量 `RIG_CLIENT_CERT` 未设置
- **THEN** CLI SHALL 从 `~/.rig/client.crt` 读取证书文件内容

#### Scenario: CA cert 加载优先级
- **WHEN** 环境变量 `RIG_CA_CERT` 已设置（值为 PEM 文本内容）
- **THEN** CLI SHALL 直接使用该 PEM 内容作为 root certificates，不读取文件系统

#### Scenario: CA cert 文件 fallback
- **WHEN** 环境变量 `RIG_CA_CERT` 未设置
- **THEN** CLI SHALL 从 `~/.rig/ca.crt` 读取 CA 证书文件内容
