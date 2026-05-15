## Why

PRD FR34 要求用户能查看信息源健康状态，FR38 要求系统能记录信息源执行日志。当前系统已经记录 `PipelineRun`、`NodeRun`，并在 `Briefing.metadata_.failed_sources` 保存失败源原因，但缺少面向用户和 API 的健康汇总契约。

## What Changes

- 新增信息源健康监控能力，按信息源展示最近运行、成功率和最近失败原因。
- 新增信息源执行日志查询能力，复用 `NodeRun`/`PipelineRun` 作为第一版日志来源。
- 健康状态优先从现有运行记录和 `Briefing.metadata_.failed_sources` 派生，不引入新外部依赖。
- 不改变现有管道执行、简报生成和结果浏览语义。

## Capabilities

### New Capabilities
- `source-health-monitoring`: 覆盖信息源健康状态汇总、最近失败原因展示和信息源执行日志查询。

### Modified Capabilities

## Impact

- 影响本机 Web 控制台和 API：需要新增健康状态与执行日志入口。
- 影响 repository 查询层：需要按信息源读取最近 `NodeRun`、关联 `PipelineRun`，并读取最新 `Briefing.metadata_.failed_sources`。
- 不需要新增外部依赖。
- 预期不需要新表；若实现阶段发现 `NodeRun.node_name` 无法稳定映射到配置源名称，必须在设计中补充 schema 变更理由后再实施。
