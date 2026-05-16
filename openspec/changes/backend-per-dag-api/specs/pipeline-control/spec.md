## MODIFIED Requirements

### Requirement: Manual run control
系统 SHALL 支持用户从 Web 控制台或 API 手动运行指定 DAG。

#### Scenario: Start manual run for named DAG
- **WHEN** 没有该 DAG 的运行中任务且用户触发手动运行
- **THEN** 系统 SHALL 启动指定 DAG 并返回新 cycle_id

#### Scenario: Reject concurrent run for same DAG
- **WHEN** 指定 DAG 已有运行中任务且用户再次触发手动运行
- **THEN** 系统 MUST 拒绝并返回当前运行中的 cycle_id

### Requirement: Stop current run
系统 SHALL 支持用户停止指定 DAG 的当前运行。

#### Scenario: Stop running cycle for named DAG
- **WHEN** 用户请求停止指定 DAG 且该 DAG 存在运行中任务
- **THEN** 系统 SHALL 请求取消该 DAG 的运行，并将运行记录最终标记为 `cancelled` 或 `failed`

#### Scenario: Stop with no active run for named DAG
- **WHEN** 用户请求停止指定 DAG 且该 DAG 没有运行中任务
- **THEN** 系统 SHALL 返回无活动运行状态

### Requirement: Runtime status display
系统 SHALL 展示指定 DAG 的当前运行状态和最近运行记录。

#### Scenario: View per-DAG pipeline status
- **WHEN** 用户查询指定 DAG 的管道状态
- **THEN** 系统 SHALL 展示该 DAG 的 scheduler 是否活跃、当前 cycle_id 和该 DAG 的最近运行列表

### Requirement: Persistent pipeline runs
系统 SHALL 持久化每次管道运行的 cycle_id、dag_name、触发来源、状态、开始时间、结束时间和错误信息。

#### Scenario: Record manual run with dag_name
- **WHEN** 用户手动触发指定 DAG 运行
- **THEN** 系统 MUST 创建一条包含 `dag_name` 和 trigger 为 `manual` 的运行记录

#### Scenario: Record failed run with dag_name
- **WHEN** 指定 DAG 运行失败
- **THEN** 系统 MUST 将运行记录状态标记为 `failed` 并保存错误信息和 `dag_name`
