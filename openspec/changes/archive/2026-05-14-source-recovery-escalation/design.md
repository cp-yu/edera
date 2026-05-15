## Context

现有系统已经有信息源健康页/API、`source_execution_logs()`、`source_health_summary()`、`PipelineRun`、`NodeRun` 和 `Briefing.metadata_.failed_sources`。这些足够表达 FR35-FR37 的最小闭环：执行时尝试有限恢复，结果落到现有运行上下文；无法恢复时在 source health 中升级给用户；用户需要外部协助时生成一个可移交的修复任务包。

## Goals / Non-Goals

**Goals:**
- 把自动恢复限定在确定安全的源级异常，不改变 DAG 拓扑。
- 让用户能在现有 source health 页面/API 看见恢复状态、升级状态和 handoff 状态。
- 用现有 `PipelineRun`、`NodeRun`、`Briefing.metadata_`、配置文件和 workspace 文件完成记录与交接。

**Non-Goals:**
- 不新增数据库表、队列、通用 incident 模型或多用户审批流。
- 不自动修改信息源配置；外部修复任务只生成交接包。
- 不把所有节点失败都纳入恢复机制，本次只覆盖已配置 source 的执行异常。

## Decisions

1. 恢复状态写入 `Briefing.metadata_`，不扩展数据库 schema。
   - 理由：当前 health API 已读取 `Briefing.metadata_.failed_sources`，同一位置可以附带 `source_recovery`、`escalated_sources`、`repair_tasks`，避免新表和迁移。
   - 备选：新增 `SourceIncident` 表。拒绝，FR35-FR37 不需要独立生命周期和查询维度。

2. `NodeRun` 仍表示最终节点结果，恢复细节作为源级 metadata 暴露。
   - 理由：`NodeRun.status` 只有单值，适合表达最终 succeeded/failed；尝试次数、恢复动作、升级原因放进 metadata 更直接。
   - 备选：为每次重试创建额外 `NodeRun`。拒绝，会污染现有按节点查询和成功率计算。

3. 外部修复任务生成 workspace 文件，并在 API 返回任务路径与 payload 摘要。
   - 理由：项目已有 `workspace_root` 概念，文件交接不需要引入外部服务依赖，外部辅助能力可以读取同一台机器上的任务包。
   - 备选：直接调用外部模型或工单系统。拒绝，本需求只要求 handoff，不要求外部执行。

## Risks / Trade-offs

- [Risk] `Briefing.metadata_` 变大且结构未受数据库约束 → 在代码中集中构造固定字段，测试字段兼容性。
- [Risk] 自动恢复误掩盖持续故障 → 记录恢复动作和 attempt_count，并在超过阈值时仍升级给用户。
- [Risk] handoff 文件泄露配置细节 → 只包含该 source 的最小配置片段、错误、日志上下文和修复目标，不写入无关 portfolio 内容。

## Migration Plan

无需数据库迁移。实现时为缺失的新 metadata 字段提供空默认；旧简报继续按现有失败源逻辑展示。回滚时删除新增页面/API逻辑后，旧数据仍可被现有 source health 功能读取。

## Open Questions

- 外部修复任务目录默认使用 `workspace_root/source-repair-tasks`，还是需要单独配置键；实现前可按最小配置变更确认。
