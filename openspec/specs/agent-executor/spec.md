# agent-executor Specification

## Purpose
此规约记录变更 core-architecture-overhaul 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Agent 节点独立执行分支
Executor SHALL 对 `AgentNodeConfig` 类型的节点走独立执行分支，不通过 handler registry，而是直接启动 subprocess 调用 pi CLI。

#### Scenario: Agent 节点执行路径
- **WHEN** executor 执行一个 `type: agent` 的节点
- **THEN** 系统 SHALL 启动 subprocess 调用 `pi` 命令，而非从 handler registry 加载 handler

#### Scenario: Function 节点仍走 handler registry
- **WHEN** executor 执行一个 `type: function` 的节点
- **THEN** 系统 SHALL 从 handler registry 加载 handler 并调用，保持现有行为

### Requirement: Pi CLI subprocess 配置
Agent 节点执行时，系统 SHALL 构造 pi CLI 命令，包含 `--session-dir`、`--model` 参数，并根据 session 是否存在决定是否传递 `--continue` 参数。

#### Scenario: 首次执行不带 continue
- **WHEN** agent 节点首次执行（session 不存在）
- **THEN** pi 命令 SHALL 不包含 `--continue` 参数

#### Scenario: Resume 执行带 continue
- **WHEN** agent 节点 resume 执行（session 已存在）
- **THEN** pi 命令 SHALL 包含 `--continue` 参数

### Requirement: Workdir 和 Session 分离
Agent 节点 SHALL 支持 `workdir` 字段（用户配置的工作目录）和 session 存储路径（daemon 自动管理）的分离。Subprocess 的 cwd SHALL 设置为 `workdir`，`--session-dir` 参数指向 daemon data dir 下的路径。

#### Scenario: Workdir 设置为 subprocess cwd
- **WHEN** agent 节点配置了 `workdir: /path/to/project`
- **THEN** subprocess 的 cwd SHALL 为 `/path/to/project`

#### Scenario: Session 路径由 daemon data dir 管理
- **WHEN** agent 节点执行
- **THEN** `--session-dir` 参数 SHALL 指向 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/{cycle_id}/`

### Requirement: 实时 Stdout Streaming
Agent 节点执行时，系统 SHALL 实时读取 subprocess 的 stdout，逐行转发到 event bus。

#### Scenario: Stdout 逐行转发
- **WHEN** pi CLI 输出一行文本到 stdout
- **THEN** executor SHALL 立即读取该行并发送到 event bus，不等待进程结束

### Requirement: 环境变量注入
Agent 节点执行时，系统 SHALL 注入环境变量：`EDERA_CLIENT_CERT`（PEM 内容）、`EDERA_CLIENT_KEY`（PEM 内容）、`EDERA_CA_CERT`（PEM 内容）、`EDERA_SERVER_ADDR`、`EDERA_IDENTITY`（值为 `node:{instance_id}`）。

#### Scenario: 证书 PEM 内容注入
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `EDERA_CLIENT_CERT` SHALL 包含 server 签发的短期证书 PEM 文本内容

#### Scenario: 私钥 PEM 内容注入
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `EDERA_CLIENT_KEY` SHALL 包含对应私钥的 PEM 文本内容

#### Scenario: CA cert PEM 内容注入
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 `EDERA_CA_CERT` SHALL 包含 server CA cert 的 PEM 文本内容

#### Scenario: Identity 注入
- **WHEN** agent 节点启动
- **THEN** subprocess 环境变量 SHALL 包含 `EDERA_IDENTITY=node:{instance_id}`

### Requirement: Stop 生命周期
系统 SHALL 支持通过 SIGTERM 信号停止 agent 节点的 subprocess。Pi CLI SHALL 在收到 SIGTERM 后保存 session 并优雅退出。

#### Scenario: Stop 发送 SIGTERM
- **WHEN** 用户调用 stop API 停止 agent 节点
- **THEN** executor SHALL 向 subprocess 发送 SIGTERM 信号

### Requirement: Resume 生命周期
系统 SHALL 支持 resume agent 节点，通过启动新的 subprocess 并传递 `--continue` 参数和可选的新 prompt。

#### Scenario: Resume 启动新进程
- **WHEN** 用户调用 resume API 恢复 agent 节点
- **THEN** executor SHALL 启动新的 pi subprocess，传递 `--continue` 和 session 路径

#### Scenario: Resume 注入新 prompt
- **WHEN** resume API 包含 `prompt` 参数
- **THEN** 新 subprocess SHALL 将该 prompt 作为输入传递给 pi CLI
