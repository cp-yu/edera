## Why

FR43 要求用户能复盘历史建议与实际价格走势是否一致。当前系统能展示 `Advice` 及证据链，但没有把建议方向和后续价格移动放在同一处对比，用户无法判断历史建议是 aligned、diverged 还是缺少可判定价格数据。

## What Changes

- 增加基于本地价格快照/历史输入的建议价格对比，不默认依赖实时外部行情。
- 对每条历史 `Advice` 按 `stock_code`、`direction`、`created_at`、`data_window_end` 和配置的 horizon 计算 verdict：`aligned`、`diverged` 或 `unknown`。
- 在结果浏览 API 和 WebUI 中展示 verdict、基准价、horizon 价、价格变动百分比和 unknown 原因。
- 复用现有结果浏览页面、建议详情页面和本机 API，不引入复杂图表系统。
- 保持现有 `Advice` 数据结构兼容；首版可由配置文件指向 CSV/YAML 价格历史输入。

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `trade-advisory`: 增加历史建议与本地价格历史的方向一致性判定。
- `result-explorer`: 在现有结果浏览 API 和 WebUI 中展示建议价格对比结果。

## Impact

- **代码**: 预计修改配置 schema/loader、建议对比服务、结果浏览 routes 和 templates；不需要新数据库表。
- **配置/数据**: 新增可配置的本地 CSV/YAML 价格历史输入路径、默认 horizon 和最小变动阈值。
- **API**: 扩展 `/api/results`、`/api/advices`、`/api/advices/{id}` 返回 comparison 字段；可选增加轻量查询参数控制 horizon。
- **WebUI**: 结果页建议列表和建议详情页展示 comparison verdict 及关键价格字段。
- **测试**: 使用固定价格 fixture 覆盖 buy/sell/hold 的 aligned/diverged/unknown；不访问外部行情。
- **非目标**: 不接入实时行情、不绘制复杂价格图、不回填或重写历史 `Advice` 记录。
