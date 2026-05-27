## MODIFIED Requirements

### Requirement: CLI binary 入口
系统 SHALL 提供名为 `rig` 的 CLI binary，作为 agent 和人类访问 Edera 控制面能力的统一入口。`rig` 是控制命令名，不是项目 canonical name。

#### Scenario: CLI 可执行
- **WHEN** 用户或 agent 在终端执行 `rig --help`
- **THEN** 系统 SHALL 输出可用子命令列表（entity、node、dag）

#### Scenario: 版本查询
- **WHEN** 用户执行 `rig --version`
- **THEN** 系统 SHALL 输出当前版本号

#### Scenario: Project command separate from control command
- **WHEN** 用户需要启动 Edera 服务入口
- **THEN** 用户 SHALL 使用 `edera` console script
- **AND** `rig` SHALL 保持为控制面 CLI

### Requirement: gRPC Client 实现
`rig` CLI SHALL 作为 gRPC client 连接 rig daemon。证书加载语义：gRPC client 层 SHALL 仅从环境变量读取 PEM 内容，不读文件系统；文件读取由 CLI 入口层在 dispatch 子命令前显式完成（针对 human-facing 子命令）。控制面身份、证书和连接环境变量 SHALL 继续使用 `RIG_*` 前缀，不迁移到 `EDERA_*`。

#### Scenario: gRPC 连接 daemon
- **WHEN** 用户执行任意 rig 命令
- **THEN** CLI SHALL 通过 gRPC 连接 daemon，使用 mTLS 认证

#### Scenario: gRPC client 层只看环境变量
- **WHEN** `RigGrpcClient` 实例化（非 `force_insecure` 模式、非 dev 模式）
- **THEN** 系统 SHALL 仅从 `RIG_CLIENT_CERT` / `RIG_CLIENT_KEY` / `RIG_CA_CERT` 环境变量读取 PEM 内容，SHALL NOT 访问 `~/.rig/` 或任何文件系统路径

#### Scenario: 环境变量 PEM 内容缺失即失败
- **WHEN** `RIG_CLIENT_CERT`、`RIG_CLIENT_KEY`、`RIG_CA_CERT` 任一环境变量未设置，且未启用 `force_insecure` / `allow_insecure` / dev 模式
- **THEN** `RigGrpcClient` SHALL 抛出 `FileNotFoundError`（或等价错误），SHALL NOT 静默回退到任何文件路径

#### Scenario: 人类 CLI 入口显式注入
- **WHEN** 用户执行 human-facing 子命令（如 `rig entity list`），且环境变量 `RIG_CLIENT_CERT` 等未预先设置
- **THEN** CLI 入口层 SHALL 在调用 `RigGrpcClient` 前读取 `~/.rig/client.crt`、`~/.rig/client.key`、`~/.rig/ca.crt` 内容并写入对应环境变量

#### Scenario: 环境变量已设置时不覆盖
- **WHEN** 用户执行 human-facing 子命令，且 `RIG_CLIENT_CERT` 环境变量已显式设置
- **THEN** CLI 入口层 SHALL NOT 读取 `~/.rig/client.crt`，SHALL 保留环境变量原值

#### Scenario: bootstrap 子命令跳过注入
- **WHEN** 用户执行 `rig client init` 或 `rig daemon` 子命令
- **THEN** CLI 入口层 SHALL NOT 读取 `~/.rig/` 文件，SHALL NOT 写入 `RIG_CLIENT_CERT` 等环境变量
