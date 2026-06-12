## MODIFIED Requirements

### Requirement: Pi CLI subprocess 配置
Agent 节点执行时，系统 SHALL 构造 pi CLI 命令，包含 `--session-dir`、`--model` 参数。当目标会话已有登记的 session id 时，命令 SHALL 包含 `--session <session-id>` 精确续接该会话；无登记时不传，由 pi 创建新会话。MUST NOT 依赖 `--continue` 的目录扫描式自动续接。

#### Scenario: 首次执行不带 session 参数
- **WHEN** agent 节点执行时其 session 组在当前目标会话中无登记的 session id
- **THEN** pi 命令 SHALL 不包含 `--session` 参数，pi 创建新会话

#### Scenario: 续接执行精确指定会话
- **WHEN** agent 节点执行时目标会话已有登记的 session id `S`
- **THEN** pi 命令 SHALL 包含 `--session S`

### Requirement: Resume 生命周期
系统 SHALL 支持 resume agent 节点，通过启动新的 subprocess、以登记的 session id 精确续接原会话，并传递可选的新 prompt。

#### Scenario: Resume 启动新进程
- **WHEN** 用户调用 resume API 恢复 agent 节点
- **THEN** executor SHALL 启动新的 pi subprocess，以原会话的 session id 续接

#### Scenario: Resume 注入新 prompt
- **WHEN** resume API 包含 `prompt` 参数
- **THEN** 新 subprocess SHALL 将该 prompt 作为输入传递给 pi CLI

## ADDED Requirements

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
