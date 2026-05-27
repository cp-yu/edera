## Why

`/results` 在成功返回空结果对象时只显示标题，用户无法判断是前端未渲染、后端失败还是当前数据库没有可展示结果。信息源日志同时存在 API 字段与前端类型不一致、普通节点混入信息源日志、时间字段为空导致页面空列的问题。

## What Changes

- 调整结果浏览页的成功空数据态：当 `/api/results` 返回有效对象但没有 `briefing`、`briefings`、`advices`、`events`、`summary_items` 时，页面 SHALL 显式展示“当前数据库没有可展示结果”类占位内容。
- 让结果浏览页消费 `/api/results` 已返回的核心字段，包括 `metadata_bar`、`briefings`、`summary_items`、`failed_sources`，避免后端有数据但前端不展示。
- 对齐信息源执行日志契约：API、类型定义和页面使用统一的 `status` 字段，不再读取不存在的 `node_status`。
- 限制信息源执行日志只返回或展示与已配置信息源相关的记录，不把普通 DAG 节点实例当成信息源日志。
- 对 `started_at=null` 的历史日志提供显示容错，优先展示 `started_at`，缺失时使用 `ended_at` 或明确的无开始时间占位。
- 不迁移历史数据库，不修改 `config/system.toml` 的 `database_url`；当前库无结果时只改善可见反馈。

## Capabilities

### New Capabilities

### Modified Capabilities
- `result-explorer`: 结果首页成功空态和已返回结果字段的展示契约。
- `source-health-monitoring`: 信息源执行日志 API 字段、过滤范围和时间容错契约。
- `sources-monitor-ui`: 信息源页面执行日志状态字段和时间空值展示契约。

## Impact

- 影响前端结果页：`apps/web-console/src/features/results/ResultsPage.tsx`。
- 影响前端信息源页与类型：`apps/web-console/src/features/sources/SourcesPage.tsx`、`apps/web-console/src/api/types.ts`。
- 影响信息源日志查询：`packages/core/src/edera_core/storage/repository.py` 中 `source_execution_logs()` 及相关日志 payload。
- 可能增加或调整 Web Console 的 Playwright 测试，以及 core repository/API 单元测试。
- 不引入新依赖，不执行数据库迁移。
