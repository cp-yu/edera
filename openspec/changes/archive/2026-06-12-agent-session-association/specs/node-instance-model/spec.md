## ADDED Requirements

### Requirement: Session 字段
`DagNodeInstance.config` SHALL 支持 `session` 字段（可选字符串），声明 agent 节点的会话关联。合法格式为组名 `<group>`、跨 DAG 引用 `<dag_name>/<group>@latest` 或 `<dag_name>/<group>@list`；其他格式 MUST 拒绝保存并提示格式错误。

#### Scenario: 组名配置
- **WHEN** 用户为 agent 节点实例设置 `session: task-1`
- **THEN** 系统 SHALL 保存到 DAG YAML 的实例 `config` 中

#### Scenario: 跨 DAG 引用配置
- **WHEN** 用户为 agent 节点实例设置 `session: relay-main/task-1@latest`
- **THEN** 系统 SHALL 保存到 DAG YAML 的实例 `config` 中

#### Scenario: 非法格式拒绝
- **WHEN** 用户设置 `session` 为非法格式（如 `a/b/c@latest`、`task-1@unknown`）
- **THEN** 系统 SHALL 拒绝保存并提示格式错误

## REMOVED Requirements

### Requirement: Session_dir 字段
**Reason**: `session_dir` 字段废弃，会话关联由 `session` 字段承载，术语统一为 session。
**Migration**: 使用 `DagNodeInstance.config.session` 字段。
