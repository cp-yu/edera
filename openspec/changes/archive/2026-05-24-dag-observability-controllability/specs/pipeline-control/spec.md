## MODIFIED Requirements

### Requirement: Stop current run

系统 SHALL 支持用户停止指定 DAG 的当前运行，MUST 支持 soft stop（等当前节点完成）和 hard stop（立即 cancel）两种模式。

#### Scenario: Soft stop 指定 DAG

- **WHEN** 用户请求停止指定 DAG（`force: false` 或无 body）且该 DAG 存在运行中任务
- **THEN** 系统 MUST 设置 stop event，等待当前正在执行的节点完成后终止 run，将运行记录标记为 `cancelled`

#### Scenario: Hard stop 指定 DAG

- **WHEN** 用户请求停止指定 DAG（`force: true`）且该 DAG 存在运行中任务
- **THEN** 系统 MUST 立即 cancel 运行 task，将运行记录标记为 `cancelled`

#### Scenario: Stop with no active run for named DAG

- **WHEN** 用户请求停止指定 DAG 且该 DAG 没有运行中任务
- **THEN** 系统 SHALL 返回无活动运行状态

### Requirement: Persistent pipeline runs

系统 SHALL 持久化每次管道运行的 cycle_id、dag_name、触发来源、状态、开始时间、结束时间、错误信息和 retry_of（nullable）。

#### Scenario: Record retry run

- **WHEN** 系统创建 retry run
- **THEN** 系统 MUST 创建一条 PipelineRun 记录，trigger 为 `"retry"`，`retry_of` 指向被重试的原始 cycle_id

#### Scenario: Record manual run with dag_name

- **WHEN** 用户手动触发指定 DAG 运行
- **THEN** 系统 MUST 创建一条包含 `dag_name` 和 trigger 为 `manual` 的运行记录，`retry_of` 为 null
