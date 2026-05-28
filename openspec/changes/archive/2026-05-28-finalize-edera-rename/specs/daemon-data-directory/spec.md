## MODIFIED Requirements

### Requirement: Daemon 数据目录配置
`edera-server` SHALL 使用独立的数据目录存储 CA、server cert 和 session 数据，与客户端家目录 `~/.edera/` 物理分离。控制面连接和证书环境变量 SHALL 使用 `EDERA_*` 前缀。

#### Scenario: 命令行参数指定 data dir
- **WHEN** 用户启动 `edera-server` 时传入 `--data-dir /var/lib/edera-server`
- **THEN** server SHALL 使用 `/var/lib/edera-server` 作为数据目录

#### Scenario: 环境变量指定 data dir
- **WHEN** 命令行参数未传 `--data-dir`，但环境变量 `EDERA_DATA_DIR=/var/lib/edera-server` 已设置
- **THEN** server SHALL 使用 `/var/lib/edera-server` 作为数据目录

#### Scenario: 默认 data dir
- **WHEN** 命令行参数和环境变量均未设置
- **THEN** server SHALL 使用 `~/.local/share/edera-server/` 作为数据目录

### Requirement: Server 证书按需生成
`edera-server` 启动时 SHALL 检查 server cert 是否存在，不存在则使用 CA 签发，CN 为 `edera-server`，SAN 由 `EDERA_SERVER_PUBLIC_HOST` 环境变量控制。

#### Scenario: 首次启动生成 server cert
- **WHEN** server 首次启动，`${data_dir}/server.crt` 不存在
- **THEN** server SHALL 使用内部 CA 签发 server cert，CN=`edera-server`，SAN 包含 `localhost` 和 `EDERA_SERVER_PUBLIC_HOST` 指定的主机名

### Requirement: Session 路径基于 data dir
Agent session 存储路径 SHALL 位于 `edera-server` data dir 下，绝对路径由 server 决定，agent subprocess 不假设位置。

#### Scenario: Session 路径
- **WHEN** server 为 agent 节点分配 session 路径
- **THEN** session 路径 SHALL 为 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/{cycle_id}/`
- **AND** server SHALL 通过 agent subprocess 的 `--session-dir` 参数传递该绝对路径
