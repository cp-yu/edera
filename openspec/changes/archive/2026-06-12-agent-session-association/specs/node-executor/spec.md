## MODIFIED Requirements

### Requirement: Agent 节点 workdir 和 session 分离
Node executor SHALL 为 agent 节点设置 subprocess cwd 为 `workdir`（用户配置），`--session-dir` 参数指向 server 决定的绝对路径 `${EDERA_DATA_DIR}/sessions/{dag_name}/{group}/{run_id}/`（`group` 为 session 组名，未声明时为 `instance_id`）。未配置 `workdir` 时 cwd SHALL 为该节点的 invocation 目录 `{session_dir}/invocations/{node_id}/`。MUST NOT 将 session 目录本身作为 cwd，MUST NOT 假设路径在客户端家目录下。

#### Scenario: Workdir 设置为 cwd
- **WHEN** agent 节点配置 `workdir: /path/to/project`
- **THEN** executor SHALL 设置 subprocess cwd 为 `/path/to/project`

#### Scenario: 未配置 workdir 时默认为 invocation 目录
- **WHEN** agent 节点未配置 `workdir`
- **THEN** executor SHALL 设置 subprocess cwd 为 `{session_dir}/invocations/{node_id}/`

#### Scenario: Session 路径由 server 管理
- **WHEN** agent 节点执行
- **THEN** executor SHALL 使用 server 决定的绝对路径作为 `--session-dir`，路径形如 `${EDERA_DATA_DIR}/sessions/{dag_name}/{group}/{run_id}/`
- **AND** executor MUST NOT 使用 `~/.rig/sessions/{...}` 或 `~/.edera/sessions/{...}` 路径模板

## ADDED Requirements

### Requirement: Session 引用解析
Node executor SHALL 在执行 agent 节点前解析实例的 `session` 字段：组名解析为当前 run 的组路径；`@latest` / `@list` 引用通过 session run 注册表解析为源组会话。未声明 `session` 的节点 SHALL 使用按 `instance_id` 推导的路径，行为不变。

#### Scenario: 组名解析为当前 run 组路径
- **WHEN** 实例声明 `session: task-1`，当前 run 为 `run-1`
- **THEN** executor SHALL 使用 `${EDERA_DATA_DIR}/sessions/{dag_name}/task-1/run-1/` 作为 session 目录

#### Scenario: 跨 DAG 引用经注册表解析
- **WHEN** 实例声明 `session: relay-main/task-1@latest`
- **THEN** executor SHALL 查询注册表获取源组最近 `completed` run 的 session id 与路径

#### Scenario: 未声明 session 行为不变
- **WHEN** 实例未声明 `session` 字段
- **THEN** executor SHALL 按 `instance_id` 推导 session 路径，与既有行为一致

## REMOVED Requirements

### Requirement: Session_dir 解析与传递
**Reason**: `session_dir` 字段废弃，会话定位由 `session` 字段与注册表解析承载。
**Migration**: 使用 `session` 字段声明组名或跨 DAG 引用；绝对路径直传能力不再提供。

### Requirement: 自动 --continue 判定
**Reason**: 共享会话目录下按 `.jsonl` 存在性判定有歧义，可能续接到错误会话。
**Migration**: 续接以注册表登记的 session id 显式定位（见 agent-executor 的 Pi CLI subprocess 配置）。
