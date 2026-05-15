## ADDED Requirements

### Requirement: Source recovery execution recording
系统 SHALL 将源级自动恢复尝试关联到现有管道运行上下文，MUST 通过 `PipelineRun.cycle_id`、对应 source 的 `NodeRun` 和 `Briefing.metadata_` 追溯恢复结果。

#### Scenario: Record successful recovery in pipeline context
- **WHEN** 某信息源在同一 cycle 内经过自动恢复后成功
- **THEN** 系统 SHALL 将对应 `NodeRun` 的最终状态记录为 `succeeded`，并在 `Briefing.metadata_` 中记录该 source 的恢复尝试摘要

#### Scenario: Record exhausted recovery in pipeline context
- **WHEN** 某信息源自动恢复尝试耗尽后仍失败
- **THEN** 系统 SHALL 将对应 `NodeRun` 的最终状态记录为 `failed`，并在 `Briefing.metadata_` 中记录 attempt_count、恢复失败原因和升级状态

#### Scenario: Preserve cycle traceability for repair handoff
- **WHEN** 用户生成外部修复任务交接包
- **THEN** 系统 SHALL 在交接包中包含最近失败 `PipelineRun.cycle_id` 和对应 `NodeRun` 错误，以便外部辅助能力追溯执行上下文
