## ADDED Requirements

### Requirement: Source recovery status
系统 SHALL 在信息源健康状态中展示最近一次源级自动恢复结果，MUST 包含 source_name、cycle_id、recovery_status、attempt_count、recoverable_reason、latest_failure_reason 和 updated_at。

#### Scenario: Show recovered source
- **WHEN** 信息源执行异常经过自动恢复后在同一 cycle 内成功产出数据
- **THEN** 系统 SHALL 在 source health API 和页面中将该信息源展示为 `recovered`，并保留 recovery attempt_count 与 recoverable_reason

#### Scenario: Show no recovery for healthy source
- **WHEN** 信息源最近一次执行没有触发自动恢复
- **THEN** 系统 SHALL 将 recovery_status 展示为 `none`，且不得把该信息源计入失败或升级列表

### Requirement: User escalation for unrecovered source
系统 SHALL 在自动恢复无法修复信息源异常时升级给用户，MUST 复用现有 source health 页面/API 展示 source_name、cycle_id、失败原因、已尝试恢复动作、下一步建议和是否可生成外部修复任务。

#### Scenario: Escalate after recovery exhausted
- **WHEN** 信息源异常属于可恢复范围但达到配置的恢复尝试上限后仍失败
- **THEN** 系统 SHALL 将该信息源标记为 `escalated`，并在 `Briefing.metadata_.failed_sources` 中保留用户可理解的失败原因

#### Scenario: Escalate non-recoverable source failure
- **WHEN** 信息源异常不属于限定恢复范围
- **THEN** 系统 SHALL 不执行自动恢复，并直接在 source health API 和页面中展示用户升级状态

### Requirement: External source repair task handoff
系统 SHALL 允许用户为已升级的信息源生成外部修复任务交接包，MUST 包含 source 配置片段、最近 cycle_id、相关 `NodeRun` 错误、恢复尝试摘要、期望修复目标和生成时间。

#### Scenario: Create repair task for escalated source
- **WHEN** 用户为 `escalated` 信息源请求生成外部修复任务
- **THEN** 系统 SHALL 写入一个 repair task 交接文件，并在 API 返回 task_id、task_path、source_name 和 created_at

#### Scenario: Reject repair task for non-escalated source
- **WHEN** 用户为未升级的信息源请求生成外部修复任务
- **THEN** 系统 MUST 拒绝请求并返回统一 JSON error，且不得创建交接文件

#### Scenario: Preserve handoff reference in health status
- **WHEN** 信息源已经生成外部修复任务
- **THEN** 系统 SHALL 在 source health API 和页面中展示最近 repair task 的 task_id、created_at 和 task_path
