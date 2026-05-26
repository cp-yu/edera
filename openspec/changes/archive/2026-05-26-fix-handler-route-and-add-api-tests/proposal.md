# fix-handler-route-and-add-api-tests

## Problem

`/api/graph/handlers/{name}` 端点用 handler name 直接拼 `extensions/{name}/handler.py` 路径，但 handler name（manifest 中定义）≠ extension 目录名：

| Extension 目录 | Handler name (manifest) |
|---|---|
| advisor | generate-advice |
| api-fetcher | fetch-api |
| briefing-generator | generate-briefing |

导致前端请求全部 404。

## Root Cause

`routes.py:987` 硬拼路径 `config_dir(request).parent / "extensions" / name / "handler.py"`，未使用已有的 `HandlerRegistry`（它正确维护了 handler name → 实际文件路径的映射）。

## Fix

让 handler read/save 端点通过 `HandlerRegistry` 查找实际路径，而非硬拼目录名。`HandlerRegistry` 在 bootstrap 时已构建，需要在 web app 层暴露给路由使用。

## Tests

当前 web API 无路由级集成测试。新增 `tests/core/integration/test_graph_api.py`，覆盖：
- `/api/graph/handlers/{name}` — 正常读取、404
- `/api/graph/handlers/{name}` PUT — 正常保存
- `/api/graph/nodes`、`/api/graph/dags` — 基本 200 验证

## Scope

- `packages/core/src/stockimformation_core/web/app.py` — 将 handler_registry 挂到 app.state
- `packages/core/src/stockimformation_core/web/routes.py` — handler read/save 使用 registry 查路径
- `tests/core/integration/test_graph_api.py` — 新增测试文件
