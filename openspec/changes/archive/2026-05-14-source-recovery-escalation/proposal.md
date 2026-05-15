## Why

FR35-FR37 要求信息源异常后有可恢复、可上报、可交接的闭环；当前系统只展示失败原因和执行日志，无法区分已自动恢复、需要用户处理、或已生成外部修复任务的状态。

## What Changes

- 为信息源执行异常增加限定恢复范围：仅覆盖临时网络/超时、HTTP 5xx/429、空结果或解析规则失效等可安全重试的问题。
- 在恢复无法解决时，通过现有 source health 页面/API 暴露用户升级状态、失败原因、最近 cycle_id 和建议动作。
- 允许用户为不可恢复的信息源生成外部修复任务交接包，复用配置文件、`PipelineRun`、`NodeRun`、`Briefing.metadata_` 和现有 source health API。
- 不新增数据库表，不引入新的通用工单或告警系统。

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `source-health-monitoring`: 扩展信息源健康视图/API，展示恢复状态、用户升级状态和外部修复任务交接结果。
- `pipeline-control`: 扩展运行记录语义，要求恢复尝试和恢复后状态可追溯到现有 `PipelineRun`、`NodeRun` 与 `Briefing.metadata_`。

## Impact

- **代码**: 预计调整 source 节点执行/降级路径、repository 查询、`/sources` 页面、`/api/sources/health`、`/api/sources/logs`，并新增最小 handoff API。
- **数据**: 复用 `Briefing.metadata_` 记录 `source_recovery` 和 repair task 摘要；复用 `NodeRun.error` 与 `PipelineRun.cycle_id` 追溯失败，不新增表。
- **配置**: 在现有配置文件中增加恢复重试上限和外部修复任务输出位置；默认值必须保守。
- **测试**: 增加 repository、pipeline/source recovery、Web API 覆盖，验证成功恢复、升级失败和 handoff 输出。
