## Why

PRD FR42 要求 Web 界面在新结果到达时自动刷新。当前结果浏览页只在页面加载时读取一次最新 `Briefing`，用户需要手动刷新才能看到新周期产出，容易错过刚完成的管道结果。

## What Changes

- 为结果浏览页增加自动检测最新结果版本的能力。
- 当最新 `Briefing.id` 或 `created_at` 变化时，结果浏览页 SHALL 刷新当前视图并显示新结果。
- 自动刷新保持轻量实现：复用现有 Web API 和原生浏览器能力，不新增外部依赖或前端框架。
- 保持结果 deep link、筛选参数和无简报空状态兼容。

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `result-explorer`: 增加结果浏览页自动检测并刷新新 `Briefing` 的行为

## Impact

- **代码**: 预计修改 `src/stockimformation/web/routes.py`、`src/stockimformation/web/templates/results.html`，必要时补充 `src/stockimformation/web/static/styles.css`。
- **API**: 复用或轻量扩展 `GET /api/briefings/latest`，返回足够判断最新结果版本的数据。
- **测试**: 增加 Web API/HTML 集成测试，覆盖新结果版本检测和自动刷新脚本挂载条件。
- **依赖**: 不新增运行时依赖，不引入 WebSocket、SSE 或前端框架。
