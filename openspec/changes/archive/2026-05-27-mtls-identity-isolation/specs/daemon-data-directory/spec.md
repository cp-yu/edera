## ADDED Requirements

### Requirement: Daemon 数据目录配置
Daemon SHALL 使用独立的数据目录存储 CA、server cert 和 session 数据，与客户端家目录 `~/.rig/` 物理分离。

#### Scenario: 命令行参数指定 data dir
- **WHEN** 用户启动 daemon 时传入 `--data-dir /opt/rig`
- **THEN** daemon SHALL 使用 `/opt/rig` 作为数据目录

#### Scenario: 环境变量指定 data dir
- **WHEN** 命令行参数未传 `--data-dir`，但环境变量 `RIG_DAEMON_DATA_DIR=/opt/rig` 已设置
- **THEN** daemon SHALL 使用 `/opt/rig` 作为数据目录

#### Scenario: 默认 data dir 优先级
- **WHEN** 命令行参数和环境变量均未设置
- **THEN** daemon SHALL 优先尝试 `/var/lib/rig/`；若该路径不可写，回退到 `~/.local/share/rig/`

### Requirement: Daemon 数据目录结构
Daemon 数据目录 SHALL 包含 CA 证书与私钥、server 证书与私钥、session 存储子目录，所有敏感文件权限 SHALL 为 `0600`。

#### Scenario: 数据目录布局
- **WHEN** daemon 启动并初始化 data dir
- **THEN** data dir SHALL 包含 `ca.crt`、`ca.key`、`server.crt`、`server.key` 和 `sessions/` 子目录

#### Scenario: 私钥文件权限
- **WHEN** daemon 创建 `ca.key` 或 `server.key` 文件
- **THEN** 文件权限 SHALL 为 `0600`，仅 daemon 进程的 OS user 可读写

### Requirement: CA 自动生成
Daemon 启动时 SHALL 检查 `${data_dir}/ca.key` 是否存在，不存在则自动生成自签 CA。

#### Scenario: 首次启动生成 CA
- **WHEN** daemon 首次启动，`${data_dir}/ca.key` 不存在
- **THEN** daemon SHALL 生成自签 CA（RSA 2048 或 EC P-256），写入 `ca.crt` 和 `ca.key`，权限 `0600`

#### Scenario: 已有 CA 时复用
- **WHEN** daemon 启动，`${data_dir}/ca.key` 已存在
- **THEN** daemon SHALL 加载现有 CA，不再生成新的

### Requirement: Server 证书按需生成
Daemon 启动时 SHALL 检查 server cert 是否存在，不存在则使用 CA 签发，CN 为 `rig-daemon`。

#### Scenario: 首次启动生成 server cert
- **WHEN** daemon 首次启动，`${data_dir}/server.crt` 不存在
- **THEN** daemon SHALL 使用内部 CA 签发 server cert，CN=`rig-daemon`，SAN 包含 `localhost` 和监听地址

### Requirement: Session 路径基于 data dir
Agent session 存储路径 SHALL 位于 daemon data dir 下，不再使用客户端家目录。

#### Scenario: Session 路径
- **WHEN** daemon 为 agent 节点分配 session 路径
- **THEN** session 路径 SHALL 为 `${data_dir}/sessions/{dag_name}/{instance_id}/{cycle_id}/`
