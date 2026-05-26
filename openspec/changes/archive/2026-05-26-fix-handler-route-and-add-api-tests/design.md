# Design: fix-handler-route-and-add-api-tests

## Decision: 通过 HandlerRegistry 解析 handler 路径

### 方案

bootstrap 阶段已构建 `HandlerRegistry`（name → HandlerEntry(path)）。将其挂到 `app.state.handler_registry`，路由通过 registry 查找实际文件路径。

### 变更点

1. **`web/app.py`** — `create_app` 接受 `handler_registry` 参数，挂到 `app.state`
2. **`web/routes.py`** — `api_graph_handler_read` / `api_graph_handler_save` 从 `request.app.state.handler_registry` 获取 entry，用 `entry.path` 读写文件
3. **`web/deps.py`** — 新增 `handler_registry(request)` helper

### 向后兼容

- `handler_registry` 参数可选（默认 None），None 时 fallback 到原有硬拼逻辑（保护无 manifest 的 legacy extension）
- PUT save 时若 registry 无此 handler，仍按原路径创建（新 handler 场景）

## Decision: 测试策略

复用 `test_config_api.py` 的 `_copy_project_config` + `FakeController` 模式，确保 extensions 目录被复制到 tmp_path，测试真实的 handler name → path 解析链路。
