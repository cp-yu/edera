## ADDED Requirements

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
系统 SHALL 优先展示用户可理解的最近失败原因，MUST 复用 `Briefing.metadata_.failed_sources` 中的源级失败原因，并在缺失时回退到最近失败 `NodeRun.error`。

#### Scenario: Use briefing failed source reason
- **WHEN** 最新 `Briefing.metadata_.failed_sources` 包含某信息源
- **THEN** 系统 SHALL 将该值作为该信息源的最近失败原因展示

#### Scenario: Fall back to node run error
- **WHEN** 最新简报没有记录某信息源失败原因但最近相关 `NodeRun` 为 failed 且包含 error
- **THEN** 系统 SHALL 展示该 `NodeRun.error` 作为最近失败原因

### Requirement: Source execution logs
系统 SHALL 提供信息源执行日志查询，MUST 展示最近相关执行记录的 cycle_id、节点或信息源名称、状态、开始时间、结束时间和错误信息。

#### Scenario: List source execution logs
- **WHEN** 用户请求信息源执行日志
- **THEN** 系统 SHALL 返回按最近执行时间倒序排列的执行记录

#### Scenario: Filter source execution logs by source
- **WHEN** 用户按信息源名称请求执行日志
- **THEN** 系统 SHALL 仅返回与该信息源相关的执行记录

#### Scenario: Preserve pipeline context in logs
- **WHEN** 系统返回一条信息源执行日志
- **THEN** 系统 SHALL 包含关联 `PipelineRun.cycle_id` 和管道运行状态，以便用户追溯该日志所属周期
