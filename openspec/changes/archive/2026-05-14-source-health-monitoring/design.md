## Context

当前运行面已经持久化 `PipelineRun` 与 `NodeRun`：`PipelineRun` 记录周期级状态、触发来源、开始/结束时间和错误；`NodeRun` 记录节点级状态、开始/结束时间和错误。简报生成会在 `Briefing.metadata_.failed_sources` 保存本周期失败源名称与失败原因。

FR34/FR38 的第一版应利用这些事实，不扩大存储模型。健康状态是运维视图，不是新的执行系统；实现应保持在查询聚合、API 和页面展示层。

## Goals / Non-Goals

**Goals:**
- 为每个已配置信息源提供成功率、最近运行时间、最近状态和最近失败原因。
- 提供信息源执行日志列表，展示最近周期内相关 `NodeRun` 与关联 `PipelineRun` 信息。
- 明确健康数据来源：`NodeRun`/`PipelineRun` 负责执行事实，`Briefing.metadata_.failed_sources` 负责用户可读失败原因补充。

**Non-Goals:**
- 不新增自动恢复、外部修复或告警能力。
- 不引入新的任务队列、监控系统或外部依赖。
- 不重新定义 DAG 执行日志格式。
- 不变更已有简报、建议或管道控制行为。

## Decisions

1. 复用现有表，不新增 `source_health` 或 `source_execution_logs` 表。

   理由：第一版只需要展示最近执行事实、成功率和失败原因，现有 `NodeRun`、`PipelineRun`、`Briefing.metadata_.failed_sources` 已覆盖这些数据。新增表会带来 migration、回填和一致性问题，但没有新的不可派生事实。

   替代方案：新增专用日志表。拒绝原因是当前没有独立保留期、审计不可变性或跨 DAG 归因需求，属于过早建模。

2. 健康状态按配置源名称聚合，执行日志按源节点关联展示。

   理由：用户理解的是配置源，不是内部 DAG 节点。实现阶段应在配置源和采集节点之间保持最小映射：能直接匹配源名称时使用源名称；只能得到节点名时，页面必须如实展示节点名并保留失败原因。

   替代方案：把所有节点都纳入健康监控。拒绝原因是 FR34/FR38 聚焦信息源运维，分析、建议、通知节点属于管道健康，不应混入信息源健康率。

3. 成功率使用有限窗口计算。

   理由：全量历史会让早期失败长期污染当前状态，也会让查询随数据增长变慢。第一版使用最近 N 次相关执行记录计算，默认窗口由实现层常量控制，API 可暴露 limit。

   替代方案：按固定自然时间窗口计算。拒绝原因是调度频率可变，按次数更直接反映最近运行质量。

## Risks / Trade-offs

- [Risk] 现有 `NodeRun.node_name` 可能是 DAG 节点名，不是配置源名称 → Mitigation: 第一版明确映射限制，优先用 `Briefing.metadata_.failed_sources` 补足源级失败原因；若无法稳定映射，实施前补充 schema 设计。
- [Risk] 成功率窗口太小导致波动 → Mitigation: 默认使用最近多次运行，并在 API 返回窗口大小。
- [Risk] 最新简报缺失时没有 `failed_sources` → Mitigation: 健康状态仍从 `NodeRun.error` 返回最近失败原因，简报失败原因仅作为补充来源。

## Migration Plan

无需数据库 migration。实施只新增查询、API、页面和测试；回滚时移除新增入口即可，不影响既有数据。

## Open Questions

- 配置源名称到 DAG 节点名的映射是否已在当前配置结构中足够稳定；如果不稳定，实施阶段需要先补一个最小映射函数，而不是新增表。
