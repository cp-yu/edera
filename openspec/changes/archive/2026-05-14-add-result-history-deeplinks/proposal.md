## Why

`_bmad-output` 中的 Web 界面构想要求从摘要逐步展开到简报、建议和完整分析链，并支持历史简报检索与深链直达。当前 WebUI 只展示最新简报和内联证据，无法复盘历史周期，也无法从链接直接打开某条简报或建议证据链。

## What Changes

- 为结果浏览增加历史简报列表和简报详情 API/HTML 页面。
- 为建议列表增加 `stock_code`、`direction`、时间范围和 limit 过滤。
- 增加稳定的本机深链：`/results/briefings/{id}` 与 `/results/advices/{id}`。
- 在建议详情页面展示 `Advice -> AnalysisResult -> RawItem` 的完整证据链。
- 保持现有 `/results` 和 `/api/advices/{id}` 兼容。

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `result-explorer`: 增加历史简报检索、建议过滤、结果深链和渐进证据展开

## Impact

- **代码**: 修改 `src/stockimformation/models/repository.py`、`src/stockimformation/web/routes.py`、`src/stockimformation/web/templates/results.html`，新增详情模板。
- **API**: 新增 `GET /api/briefings`、`GET /api/briefings/{id}`；扩展 `GET /api/advices` 查询参数。
- **测试**: 增加 repository 和 Web API 集成测试。
- **非目标**: 不实现股价对比、实时刷新、通知推送 deep link 配置或新数据库表。
