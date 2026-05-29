# source-health-monitoring Specification

## Purpose
此规约记录变更 source-health-monitoring 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Source health summary
系统 SHALL 为用户展示已配置信息源的健康状态，MUST 包含信息源名称、最近运行状态、最近运行时间、成功率、统计窗口大小和最近失败原因。

#### Scenario: View source health summary
- **WHEN** 用户打开信息源健康状态视图
- **THEN** 系统 SHALL 按已配置信息源返回健康状态列表，并为每个信息源展示成功率和最近失败原因

#### Scenario: Compute success rate from recent executions
- **WHEN** 信息源存在最近执行记录
- **THEN** 系统 SHALL 使用最近有限窗口内的成功与失败记录计算成功率，并返回用于计算的窗口大小

#### Scenario: Show unknown health without executions
- **WHEN** 已配置信息源没有任何执行记录
- **THEN** 系统 SHALL 将该信息源展示为未知状态，成功率为空，并且不把未知状态计为失败

### Requirement: Latest source failure reason
系统 SHALL 优先从 `source_recoveries` runtime table 展示用户可理解的最近失败原因，并在缺失时回退到真实 source fetcher `NodeRun.error`。系统 MUST NOT 依赖 `Briefing.metadata_.failed_sources` 作为 source health 的事实源。

#### Scenario: Use source recovery failure reason
- **WHEN** 最近 `source_recoveries` 记录包含某信息源的 `latest_failure_reason`
- **THEN** 系统 SHALL 将该值作为该信息源的最近失败原因展示

#### Scenario: Fall back to node run error
- **WHEN** `source_recoveries` 没有记录某信息源失败原因但最近相关 source fetcher `NodeRun` 为 failed 且包含 error
- **THEN** 系统 SHALL 展示该 `NodeRun.error` 作为最近失败原因

### Requirement: Source execution logs
系统 SHALL 提供信息源执行日志查询，MUST 展示最近相关执行记录的 run_id、信息源名称、状态、开始时间、结束时间、错误信息和关联管道状态。日志 payload SHALL 使用 `status` 字段表示执行状态，MUST NOT 要求客户端读取 `node_status`。默认日志查询 SHALL 只返回与已配置信息源或 source recovery 相关的记录，不得把普通 DAG 节点实例混入信息源日志。

#### Scenario: List source execution logs
- **WHEN** 用户请求信息源执行日志
- **THEN** 系统 SHALL 返回按最近执行时间倒序排列的执行记录

#### Scenario: Filter source execution logs by source
- **WHEN** 用户按信息源名称请求执行日志
- **THEN** 系统 SHALL 仅返回与该信息源相关的执行记录

#### Scenario: Preserve DAG run context in logs
- **WHEN** 系统返回一条信息源执行日志
- **THEN** 系统 SHALL 包含关联 `DagRun.run_id` 和管道运行状态，以便用户追溯该日志所属周期

#### Scenario: Use status field in source log payload
- **WHEN** 系统返回一条信息源执行日志
- **THEN** 日志 payload SHALL 包含非空 `status` 字段，并 MUST NOT 依赖 `node_status` 表示状态

#### Scenario: Exclude ordinary node runs from source logs
- **WHEN** 默认查询信息源执行日志且数据库包含普通 DAG 节点运行记录
- **THEN** 系统 SHALL 只返回 `source_name` 属于已配置信息源或 source recovery 的日志记录

#### Scenario: Preserve readable time when start time is missing
- **WHEN** 一条信息源执行日志的 `started_at` 为空但 `ended_at` 存在
- **THEN** 系统 SHALL 保留 `ended_at`，让客户端能够显示可读时间而不是空白时间列

### Requirement: Source recovery status
系统 SHALL 在信息源健康状态中展示最近一次源级自动恢复结果，MUST 从 `source_recoveries` 读取 source_name、run_id、node_id、recovery_status、attempt_count、recoverable_reason、latest_failure_reason、escalated、escalation_reason 和 created_at。

#### Scenario: Show recovered source
- **WHEN** 信息源执行异常经过自动恢复后在同一 run 内成功产出数据
- **THEN** 系统 SHALL 在 source health API 和页面中将该信息源展示为 `recovered`，并保留 recovery attempt_count 与 recoverable_reason

#### Scenario: Show no recovery for healthy source
- **WHEN** 信息源最近一次执行没有触发自动恢复
- **THEN** 系统 SHALL 将 recovery_status 展示为 `none`，且不得把该信息源计入失败或升级列表

#### Scenario: Show escalated source from runtime table
- **WHEN** `source_recoveries.escalated` 为 true
- **THEN** 系统 SHALL 在 source health API 和页面中展示升级状态和 `escalation_reason`

### Requirement: User escalation for unrecovered source
系统 SHALL 在自动恢复无法修复信息源异常时升级给用户，MUST 复用现有 source health 页面/API 展示 source_name、run_id、失败原因、已尝试恢复动作、下一步建议和是否可生成外部修复任务。升级事实 SHALL 以 `source_recoveries` 为事实源。

#### Scenario: Escalate after recovery exhausted
- **WHEN** 信息源异常属于可恢复范围但达到配置的恢复尝试上限后仍失败
- **THEN** 系统 SHALL 将该信息源在 `source_recoveries` 中标记为 `escalated=true`，并保留用户可理解的失败原因

#### Scenario: Escalate non-recoverable source failure
- **WHEN** 信息源异常不属于限定恢复范围
- **THEN** 系统 SHALL 不执行自动恢复，并直接在 `source_recoveries` 中记录用户升级状态

### Requirement: External source repair task handoff
系统 SHALL 允许用户为已升级的信息源生成外部修复任务交接包，MUST 包含 source 配置片段、最近 run_id、相关 `NodeRun` 错误、恢复尝试摘要、期望修复目标和生成时间。

#### Scenario: Create repair task for escalated source
- **WHEN** 用户为 `escalated` 信息源请求生成外部修复任务
- **THEN** 系统 SHALL 写入一个 repair task 交接文件，并在 API 返回 task_id、task_path、source_name 和 created_at

#### Scenario: Reject repair task for non-escalated source
- **WHEN** 用户为未升级的信息源请求生成外部修复任务
- **THEN** 系统 MUST 拒绝请求并返回统一 JSON error，且不得创建交接文件

#### Scenario: Preserve handoff reference in health status
- **WHEN** 信息源已经生成外部修复任务
- **THEN** 系统 SHALL 在 source health API 和页面中展示最近 repair task 的 task_id、created_at 和 task_path
