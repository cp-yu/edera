## MODIFIED Requirements

### Requirement: Manual run control
系统 SHALL 支持用户从 Web 控制台或 API 手动运行指定 DAG。DAG run 启动时 SHALL 接受 `sourceSharedInputs`、`nodeInputs`、`appendNodes` 参数用于临时覆盖或追加节点输入。

#### Scenario: 手动运行时传递临时输入
- **WHEN** 用户通过 API 手动运行 DAG 并传入 `{sourceSharedInputs: {...}, nodeInputs: {...}}`
- **THEN** 系统 SHALL 将临时输入参数传递给 DagRunner
