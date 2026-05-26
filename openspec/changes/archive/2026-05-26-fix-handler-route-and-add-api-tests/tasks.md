# Tasks: fix-handler-route-and-add-api-tests

## T1: web app 层暴露 HandlerRegistry
- [x] `web/deps.py` 新增 `handler_registry(request)` helper
- [x] `web/app.py` 的 `create_app` 接受并挂载 `handler_registry`
- [x] 调用方（`dev.sh` / pipeline 启动）传入 bootstrap 结果的 registry

## T2: 修复 handler read/save 路由
- [x] `api_graph_handler_read` 优先从 registry 查 path，fallback 原逻辑
- [x] `api_graph_handler_save` 同理

## T3: 新增 graph API 集成测试
- [x] `tests/core/integration/test_graph_api.py`
- [x] 测试 handler read（正常 + 404）
- [x] 测试 handler save
- [x] 测试 `/api/graph/nodes`、`/api/graph/dags` 基本 200
