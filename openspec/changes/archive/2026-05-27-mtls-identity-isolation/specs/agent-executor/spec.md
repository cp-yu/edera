## MODIFIED Requirements

### Requirement: 环境变量注入
Agent 节点执行时，系统 SHALL 注入环境变量：`RIG_CLIENT_CERT`（PEM 内容）、`RIG_CLIENT_KEY`（PEM 内容）、`RIG_CA_CERT`（PEM 内容）、`RIG_DAEMON_ADDR`、`RIG_IDENTITY`（值为 `node:{instance_id}`）。

#### Scenario: 证书 PEM 内容注入
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `RIG_CLIENT_CERT` SHALL 包含 daemon 签发的短期证书 PEM 文本内容

#### Scenario: 私钥 PEM 内容注入
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `RIG_CLIENT_KEY` SHALL 包含对应私钥的 PEM 文本内容

#### Scenario: CA cert PEM 内容注入
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `RIG_CA_CERT` SHALL 包含 daemon CA cert 的 PEM 文本内容

#### Scenario: Identity 注入
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 SHALL 包含 `RIG_IDENTITY=node:{instance_id}`

### Requirement: Workdir 和 Session 分离
Agent 节点 SHALL 支持 `workdir` 字段（用户配置的工作目录）和 session 存储路径（daemon 自动管理）的分离。Subprocess 的 cwd SHALL 设置为 `workdir`，`--session-dir` 参数指向 daemon data dir 下的路径。

#### Scenario: Workdir 设置为 subprocess cwd
- **WHEN** agent 节点配置了 `workdir: /path/to/project`
- **THEN** subprocess 的 cwd SHALL 为 `/path/to/project`

#### Scenario: Session 路径由 daemon data dir 管理
- **WHEN** agent 节点执行
- **THEN** `--session-dir` 参数 SHALL 指向 `${RIG_DAEMON_DATA_DIR}/sessions/{dag_name}/{instance_id}/{cycle_id}/`
