## ADDED Requirements

### Requirement: Tools 白名单传递
Node executor SHALL 根据节点配置的 `tools` 字段生成 pi 的 `--tools` 参数。

#### Scenario: 类型层默认 tools
- **WHEN** `NodeConfig` 定义 `tools: [bash]`，实例未覆盖
- **THEN** executor SHALL 向 pi 传递 `--tools bash`

#### Scenario: 实例层覆盖 tools
- **WHEN** `NodeConfig` 定义 `tools: [bash]`，实例配置 `tools: [bash, read, edit, write]`
- **THEN** executor SHALL 使用实例配置，向 pi 传递 `--tools bash,read,edit,write`

#### Scenario: 空 tools 列表
- **WHEN** 实例配置 `tools: []`
- **THEN** executor SHALL 向 pi 传递 `--no-tools`

### Requirement: RIG_IDENTITY 环境变量注入
Node executor SHALL 在启动 pi 进程时注入 `RIG_IDENTITY` 环境变量，值为 `node:{node_id}`。

#### Scenario: 注入节点身份
- **WHEN** executor 执行节点实例 `llm-analyze`
- **THEN** executor SHALL 设置环境变量 `RIG_IDENTITY=node:llm-analyze` 后启动 pi 进程

#### Scenario: Agent 调用 rig CLI
- **WHEN** pi 进程中的 agent 执行 `rig entity get stock:AAPL`
- **THEN** `rig` CLI SHALL 读取 `RIG_IDENTITY` 环境变量，以 `node:llm-analyze` 身份执行权限检查

### Requirement: Session_dir 解析与传递
Node executor SHALL 解析 `session_dir` 配置（支持引用格式），将解析后的绝对路径传递给 pi 的 `--session-dir` 参数。

#### Scenario: 解析 latest 引用
- **WHEN** 实例配置 `session_dir: "sandbox:llm-analyze:latest"`
- **THEN** executor SHALL 查询 `llm-analyze` 节点最近一次执行的 sandbox 路径，传递给 pi

#### Scenario: 解析指定 cycle 引用
- **WHEN** 实例配置 `session_dir: "sandbox:llm-analyze:run-20260524-001"`
- **THEN** executor SHALL 构造路径 `workspace_root/sandbox/llm-analyze/run-20260524-001/sessions/`，传递给 pi

#### Scenario: 绝对路径直接传递
- **WHEN** 实例配置 `session_dir: "/data/persistent/advisor-session"`
- **THEN** executor SHALL 直接将该路径传递给 pi 的 `--session-dir`

### Requirement: 自动 --continue 判定
Node executor SHALL 检测 session_dir 中是否存在 `.jsonl` 文件，存在则向 pi 传递 `--continue` flag。

#### Scenario: 存在 session 文件
- **WHEN** session_dir 中存在 `*.jsonl` 文件
- **THEN** executor SHALL 向 pi 传递 `--continue` flag

#### Scenario: 不存在 session 文件
- **WHEN** session_dir 为空目录或仅包含非 `.jsonl` 文件
- **THEN** executor SHALL 不传 `--continue`，pi 创建新 session
