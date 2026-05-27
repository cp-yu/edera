## MODIFIED Requirements

### Requirement: Latest source failure reason
系统 SHALL 优先从 `source_recoveries` runtime table 展示用户可理解的最近失败原因，并在缺失时回退到真实 source fetcher `NodeRun.error`。系统 MUST NOT 依赖 `Briefing.metadata_.failed_sources` 作为 source health 的事实源。

#### Scenario: Use source recovery failure reason
- **WHEN** 最近 `source_recoveries` 记录包含某信息源的 `latest_failure_reason`
- **THEN** 系统 SHALL 将该值作为该信息源的最近失败原因展示

#### Scenario: Fall back to node run error
- **WHEN** `source_recoveries` 没有记录某信息源失败原因但最近相关 source fetcher `NodeRun` 为 failed 且包含 error
- **THEN** 系统 SHALL 展示该 `NodeRun.error` 作为最近失败原因

### Requirement: Source execution logs
系统 SHALL 提供信息源执行日志查询，MUST 展示最近相关执行记录的 cycle_id、source_name、source fetcher node_id、状态、开始时间、结束时间和错误信息。系统 MUST NOT 在 `node_runs` 中创建以 source_name 为 node_name 的伪记录。

#### Scenario: List source execution logs
- **WHEN** 用户请求信息源执行日志
- **THEN** 系统 SHALL 从真实 node runs 和 `source_recoveries` 返回按最近执行时间倒序排列的执行记录

#### Scenario: Filter source execution logs by source
- **WHEN** 用户按信息源名称请求执行日志
- **THEN** 系统 SHALL 仅返回与该信息源相关的 source recovery 或 source fetcher 执行记录

#### Scenario: Preserve pipeline context in logs
- **WHEN** 系统返回一条信息源执行日志
- **THEN** 系统 SHALL 包含关联 `PipelineRun.cycle_id` 和管道运行状态，以便用户追溯该日志所属周期

### Requirement: Source recovery status
系统 SHALL 在信息源健康状态中展示最近一次源级自动恢复结果，MUST 从 `source_recoveries` 读取 source_name、cycle_id、node_id、recovery_status、attempt_count、recoverable_reason、latest_failure_reason、escalated、escalation_reason 和 created_at。

#### Scenario: Show recovered source
- **WHEN** 信息源执行异常经过自动恢复后在同一 cycle 内成功产出数据
- **THEN** 系统 SHALL 在 source health API 和页面中将该信息源展示为 `recovered`，并保留 recovery attempt_count 与 recoverable_reason

#### Scenario: Show no recovery for healthy source
- **WHEN** 信息源最近一次执行没有触发自动恢复
- **THEN** 系统 SHALL 将 recovery_status 展示为 `none`，且不得把该信息源计入失败或升级列表

#### Scenario: Show escalated source from runtime table
- **WHEN** `source_recoveries.escalated` 为 true
- **THEN** 系统 SHALL 在 source health API 和页面中展示升级状态和 `escalation_reason`

### Requirement: User escalation for unrecovered source
系统 SHALL 在自动恢复无法修复信息源异常时升级给用户，MUST 复用现有 source health 页面/API 展示 source_name、cycle_id、失败原因、已尝试恢复动作、下一步建议和是否可生成外部修复任务。升级事实 SHALL 以 `source_recoveries` 为事实源。

#### Scenario: Escalate after recovery exhausted
- **WHEN** 信息源异常属于可恢复范围但达到配置的恢复尝试上限后仍失败
- **THEN** 系统 SHALL 将该信息源在 `source_recoveries` 中标记为 `escalated=true`，并保留用户可理解的失败原因

#### Scenario: Escalate non-recoverable source failure
- **WHEN** 信息源异常不属于限定恢复范围
- **THEN** 系统 SHALL 不执行自动恢复，并直接在 `source_recoveries` 中记录用户升级状态
