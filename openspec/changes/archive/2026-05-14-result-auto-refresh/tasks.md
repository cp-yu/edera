## 1. Web 自动刷新实现

- [x] 1.1 确认 `GET /api/briefings/latest` 返回 `Briefing.id` 和 `created_at`；若缺失，仅做最小 API 调整
- [x] 1.2 在 `/results` 模板输出当前结果版本和刷新检查间隔
- [x] 1.3 使用原生浏览器 API 轮询最新 `Briefing` 版本，并在版本变化时刷新当前 URL
- [x] 1.4 处理无简报和检查失败场景，保持页面可用且不显示错误页面
- [x] 1.5 如需用户可见状态，仅补充最小 CSS，不改动无关布局

## 2. 目标测试

- [x] 2.1 增加或更新 Web 集成测试，覆盖 `/api/briefings/latest` 暴露版本字段
- [x] 2.2 增加或更新结果页 HTML 测试，覆盖自动刷新脚本或 `data-*` 配置存在
- [x] 2.3 增加或更新测试，覆盖无 `Briefing` 时仍保留空状态和自动检测配置

## 3. 全量验证

- [x] 3.1 运行目标测试：`pytest tests/integration/test_web_api.py`
- [x] 3.2 运行全量测试：`pytest tests/unit tests/contract tests/integration tests/e2e`
- [x] 3.3 运行 `ruff check .`
- [x] 3.4 运行 `mypy src`

## 4. OpenSpec 收尾

- [x] 4.1 运行 `openspec validate result-auto-refresh --type change --json`
- [x] 4.2 实现完成后运行 OpenSpec verify
- [x] 4.3 验证通过后运行 OpenSpec sync
- [x] 4.4 归档完成的 change：`openspec archive result-auto-refresh`
