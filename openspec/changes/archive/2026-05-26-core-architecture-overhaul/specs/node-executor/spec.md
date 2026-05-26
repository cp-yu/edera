## ADDED Requirements

### Requirement: 按 NodeConfig type 分发执行
Node executor SHALL 根据 NodeConfig 的 type 字段分发到不同执行路径：`function` 走 handler registry，`agent` 走 subprocess pi CLI，`dag` 走递归 DagRunner。MUST NOT 统一为 function node 执行路径。

#### Scenario: Function 节点走 handler registry
- **WHEN** executor 执行 `FunctionNodeConfig` 类型节点
- **THEN** executor SHALL 通过 importlib 从 handler registry 加载 handler 模块，调用 `run(ctx: HandlerContext)`

#### Scenario: Agent 节点走 subprocess
- **WHEN** executor 执行 `AgentNodeConfig` 类型节点
- **THEN** executor SHALL 启动 subprocess 调用 pi CLI，不走 handler registry

#### Scenario: Dag 节点走递归 DagRunner
- **WHEN** executor 执行 `DagNodeConfig` 类型节点
- **THEN** executor SHALL 递归调用 DagRunner 执行目标 DAG

### Requirement: Agent 节点 workdir 和 session 分离
Node executor SHALL 为 agent 节点设置 subprocess cwd 为 `workdir`（用户配置），`--session-dir` 参数指向 daemon 管理的路径 `~/.rig/sessions/{dag_name}/{instance_id}/{cycle_id}/`。MUST NOT 将 `session_dir` 作为 cwd。

#### Scenario: Workdir 设置为 cwd
- **WHEN** agent 节点配置 `workdir: /path/to/project`
- **THEN** executor SHALL 设置 subprocess cwd 为 `/path/to/project`

#### Scenario: Session 路径由 daemon 管理
- **WHEN** agent 节点执行
- **THEN** executor SHALL 构造 session 路径 `~/.rig/sessions/{dag_name}/{instance_id}/{cycle_id}/`，传递给 pi 的 `--session-dir`
