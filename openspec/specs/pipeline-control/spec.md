## ADDED Requirements

### Requirement: Persistent pipeline runs
系统 SHALL 持久化每次管道运行的 cycle_id、触发来源、状态、开始时间、结束时间和错误信息。

#### Scenario: Record manual run
- **WHEN** 用户手动触发一次默认 DAG
- **THEN** 系统 MUST 创建一条 trigger 为 `manual` 的运行记录

#### Scenario: Record failed run
- **WHEN** 默认 DAG 运行失败
- **THEN** 系统 MUST 将运行记录状态标记为 `failed` 并保存错误信息

### Requirement: Persistent node runs
系统 SHALL 持久化每次管道运行中各 Node 的状态、开始时间、结束时间和错误信息。

#### Scenario: Record node failure
- **WHEN** 某个 Node 执行失败但 DAG 继续降级运行
- **THEN** 系统 MUST 保存该 Node 的 `failed` 状态和错误信息

### Requirement: Manual run control
系统 SHALL 支持用户从 Web 控制台手动运行一次默认 DAG。

#### Scenario: Start manual run
- **WHEN** 没有运行中的默认 DAG 且用户点击手动运行
- **THEN** 系统 SHALL 启动一次默认 DAG 并返回新 cycle_id

#### Scenario: Reject concurrent run
- **WHEN** 已有默认 DAG 正在运行且用户再次点击手动运行
- **THEN** 系统 MUST 拒绝并返回当前运行中的 cycle_id

### Requirement: Scheduler pause and resume
系统 SHALL 支持用户暂停和恢复定时调度。

#### Scenario: Pause scheduler
- **WHEN** 用户点击暂停调度
- **THEN** 系统 SHALL 暂停后续定时触发，但不取消当前正在运行的周期

#### Scenario: Resume scheduler
- **WHEN** 用户点击恢复调度
- **THEN** 系统 SHALL 恢复后续定时触发

### Requirement: Stop current run
系统 SHALL 支持用户停止当前运行中的默认 DAG。

#### Scenario: Stop running cycle
- **WHEN** 用户点击停止当前运行且存在运行中的默认 DAG
- **THEN** 系统 SHALL 请求取消当前运行，并将运行记录最终标记为 `cancelled` 或 `failed`

#### Scenario: Stop with no active run
- **WHEN** 用户点击停止当前运行且没有运行中的默认 DAG
- **THEN** 系统 SHALL 返回无活动运行状态，而不是创建新的运行记录

### Requirement: Runtime status display
系统 SHALL 展示当前调度状态、当前运行状态和最近运行记录。

#### Scenario: View pipeline status
- **WHEN** 用户打开管道控制页面
- **THEN** 系统 SHALL 展示 scheduler 是否运行、是否暂停、当前 cycle_id 和最近运行列表
