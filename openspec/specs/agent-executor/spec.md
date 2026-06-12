---
capabilities:
  - cap.core.agent-executor
---
# agent-executor Specification

## Purpose
定义 Agent 节点独立执行分支、Pi CLI subprocess 配置、Workdir 和 Session 分离、实时 Stdout Streaming等能力。
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
Agent 节点执行时，系统 SHALL 构造 pi CLI 命令，包含 `--session-dir`、`--model` 参数。当目标会话已有登记的 session id 时，命令 SHALL 包含 `--session <session-id>` 精确续接该会话；无登记时不传，由 pi 创建新会话。MUST NOT 依赖 `--continue` 的目录扫描式自动续接。

#### Scenario: 首次执行不带 session 参数
- **WHEN** agent 节点执行时其 session 组在当前目标会话中无登记的 session id
- **THEN** pi 命令 SHALL 不包含 `--session` 参数，pi 创建新会话

#### Scenario: 续接执行精确指定会话
- **WHEN** agent 节点执行时目标会话已有登记的 session id `S`
- **THEN** pi 命令 SHALL 包含 `--session S`

### Requirement: Workdir 和 Session 分离
Agent 节点 SHALL 支持 `workdir` 字段（用户配置的工作目录）和 session 存储路径（daemon 自动管理）的分离。Subprocess 的 cwd SHALL 设置为 `workdir`，`--session-dir` 参数指向 daemon data dir 下的路径。

#### Scenario: Workdir 设置为 subprocess cwd
- **WHEN** agent 节点配置了 `workdir: /path/to/project`
- **THEN** subprocess 的 cwd SHALL 为 `/path/to/project`

#### Scenario: Session 路径由 daemon data dir 管理
- **WHEN** agent 节点执行
- **THEN** `--session-dir` 参数 SHALL 指向 `${EDERA_DATA_DIR}/sessions/{dag_name}/{instance_id}/{run_id}/`

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
系统 SHALL 支持 resume agent 节点，通过启动新的 subprocess、以登记的 session id 精确续接原会话，并传递可选的新 prompt。

#### Scenario: Resume 启动新进程
- **WHEN** 用户调用 resume API 恢复 agent 节点
- **THEN** executor SHALL 启动新的 pi subprocess，以原会话的 session id 续接

#### Scenario: Resume 注入新 prompt
- **WHEN** resume API 包含 `prompt` 参数
- **THEN** 新 subprocess SHALL 将该 prompt 作为输入传递给 pi CLI

### Requirement: Invocation 产物命名空间
Agent 节点每次执行的逐次产物（prompt.md、runtime-context.json、stdout.log、result.json）SHALL 写入 `{session_dir}/invocations/{node_id}/`，不写入 session 目录根。session 目录根下共享的内容仅为会话文件（`*.jsonl`）与 `skills/`。

#### Scenario: 逐次产物写入节点专属目录
- **WHEN** agent 节点 B 执行
- **THEN** prompt.md、runtime-context.json、stdout.log SHALL 写入 `{session_dir}/invocations/B/`

#### Scenario: 同组节点产物互不覆盖
- **WHEN** 同组节点 B、D 先后在同一 session 目录中执行
- **THEN** 两者的逐次产物分别位于 `invocations/B/` 与 `invocations/D/`，互不覆盖

### Requirement: Agent 结构化输出契约
Agent 节点执行时，系统 SHALL 在 runtime-context 中注入 `result_path`（结果文件路径）与 `output_schema`（按 `output_type` 对应 entity-type schema，无 schema 时为自由 JSON），并在 prompt 尾部拼接结果写入指令。进程退出后系统 SHALL 读取结果文件并按 schema 校验：通过则节点 payload 为解析后的 JSON；文件缺失或校验失败则 payload 降级为 `{"stdout": <全部输出>}` 并在 metadata 打降级标记。

#### Scenario: 结果文件校验通过
- **WHEN** agent 在 `result_path` 写入了符合 `output_schema` 的 JSON 并正常退出
- **THEN** 节点输出 payload SHALL 为该 JSON 解析结果

#### Scenario: 结果文件缺失降级
- **WHEN** agent 正常退出但 `result_path` 不存在
- **THEN** payload SHALL 为 `{"stdout": <全部输出>}`，metadata SHALL 包含降级标记

#### Scenario: 校验失败降级
- **WHEN** `result_path` 内容不符合 `output_schema`
- **THEN** payload SHALL 降级为 `{"stdout": <全部输出>}`，metadata SHALL 包含降级标记

#### Scenario: 无 schema 时自由 JSON
- **WHEN** 节点 `output_type` 无对应 entity-type schema
- **THEN** `result_path` 中任何合法 JSON SHALL 校验通过

