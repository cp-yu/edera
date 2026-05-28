## MODIFIED Requirements

### Requirement: EDERA_IDENTITY 环境变量注入
Node executor SHALL 在启动 pi 进程时注入 `EDERA_IDENTITY` 环境变量，值为 `node:{node_id}`。

#### Scenario: 注入节点身份
- **WHEN** executor 执行节点实例 `llm-analyze`
- **THEN** executor SHALL 设置环境变量 `EDERA_IDENTITY=node:llm-analyze` 后启动 pi 进程

#### Scenario: Agent 调用 edera CLI
- **WHEN** pi 进程中的 agent 执行 `edera entity get stock:AAPL`
- **THEN** `edera` CLI SHALL 读取 `EDERA_IDENTITY` 环境变量，以 `node:llm-analyze` 身份执行权限检查

## MODIFIED Requirements

### Requirement: Agent 节点 workdir 和 session 分离
Node executor SHALL 为 agent 节点设置 subprocess cwd 为 `workdir`（用户配置），`--session-dir` 参数指向 server 决定的绝对路径 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/{cycle_id}/`。MUST NOT 将 `session_dir` 作为 cwd，MUST NOT 假设路径在客户端家目录下。

#### Scenario: Workdir 设置为 cwd
- **WHEN** agent 节点配置 `workdir: /path/to/project`
- **THEN** executor SHALL 设置 subprocess cwd 为 `/path/to/project`

#### Scenario: Session 路径由 server 管理
- **WHEN** agent 节点执行
- **THEN** executor SHALL 使用 server 决定的绝对路径作为 `--session-dir`，路径形如 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/{cycle_id}/`
- **AND** executor MUST NOT 使用 `~/.rig/sessions/{...}` 或 `~/.edera/sessions/{...}` 路径模板
