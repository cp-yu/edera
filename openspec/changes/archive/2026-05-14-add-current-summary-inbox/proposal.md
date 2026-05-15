## Why

`_bmad-output` 的 UX 规格把结果页首屏定义为“摘要列表 → 详情预览 → 证据链”的 Inbox 体验。当前 `/results` 仍以最新简报正文为主，用户不能在首屏按标的快速扫描方向、置信度、低置信度和采集降级状态。

## What Changes

- 将结果浏览首页补齐为当前结果摘要视图：按建议生成可扫描的摘要列表，并保留简报、历史和详情入口。
- 增加页面级 metadata bar，展示最新 cycle、创建时间、数据窗口、失败源数量和免责声明。
- 为建议行增加方向/置信度语义样式，使低置信度、买入、卖出、持有状态在摘要层可见。
- 保持现有 API、数据模型和 deep link 路由兼容。

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `result-explorer`: 增加当前周期摘要 Inbox、metadata bar 和 WebUI 免责声明展示要求。

## Impact

- **代码**: 修改 `src/stockimformation/web/routes.py`、`src/stockimformation/web/templates/results.html`、`src/stockimformation/web/static/styles.css`。
- **API**: 保持现有 `/api/results` 字段兼容，可追加当前摘要所需的派生字段。
- **测试**: 增加 Web 集成测试覆盖摘要视图、metadata bar、免责声明和语义状态。
- **非目标**: 不实现已读状态持久化、WebSocket 自动刷新、历史建议 vs 股价对比、Node Graph 或新数据库表。
