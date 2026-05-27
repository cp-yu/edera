## MODIFIED Requirements

### Requirement: Source execution logs
系统 SHALL 提供信息源执行日志查询，MUST 展示最近相关执行记录的 cycle_id、信息源名称、状态、开始时间、结束时间、错误信息和关联管道状态。日志 payload SHALL 使用 `status` 字段表示执行状态，MUST NOT 要求客户端读取 `node_status`。默认日志查询 SHALL 只返回与已配置信息源或 source recovery 相关的记录，不得把普通 DAG 节点实例混入信息源日志。

#### Scenario: List source execution logs
- **WHEN** 用户请求信息源执行日志
- **THEN** 系统 SHALL 返回按最近执行时间倒序排列的执行记录

#### Scenario: Filter source execution logs by source
- **WHEN** 用户按信息源名称请求执行日志
- **THEN** 系统 SHALL 仅返回与该信息源相关的执行记录

#### Scenario: Preserve pipeline context in logs
- **WHEN** 系统返回一条信息源执行日志
- **THEN** 系统 SHALL 包含关联 `PipelineRun.cycle_id` 和管道运行状态，以便用户追溯该日志所属周期

#### Scenario: Use status field in source log payload
- **WHEN** 系统返回一条信息源执行日志
- **THEN** 日志 payload SHALL 包含非空 `status` 字段，并 MUST NOT 依赖 `node_status` 表示状态

#### Scenario: Exclude ordinary node runs from source logs
- **WHEN** 默认查询信息源执行日志且数据库包含普通 DAG 节点运行记录
- **THEN** 系统 SHALL 只返回 `source_name` 属于已配置信息源或 source recovery 的日志记录

#### Scenario: Preserve readable time when start time is missing
- **WHEN** 一条信息源执行日志的 `started_at` 为空但 `ended_at` 存在
- **THEN** 系统 SHALL 保留 `ended_at`，让客户端能够显示可读时间而不是空白时间列
