## 1. Repository 查询

- [x] 1.1 新增 `list_briefings` 与 `get_briefing`
- [x] 1.2 扩展 `list_advices` 支持 stock_code、direction、created_at 起止时间和 limit
- [x] 1.3 补充 repository 单元测试覆盖排序、过滤和时间范围

## 2. Web API 与 HTML 深链

- [x] 2.1 新增 `/api/briefings` 和 `/api/briefings/{id}`
- [x] 2.2 扩展 `/api/advices` 查询参数
- [x] 2.3 新增 `/results/briefings/{id}` 和 `/results/advices/{id}` HTML 路由
- [x] 2.4 更新结果页模板，加入过滤表单、历史简报列表和详情链接
- [x] 2.5 新增建议详情模板，展示 Advice、AnalysisResult 和 RawItem 证据链

## 3. 验证与归档

- [x] 3.1 补充 Web API 集成测试覆盖简报历史、建议过滤、详情 deep link 和 not found
- [x] 3.2 运行 `pytest tests/unit tests/contract tests/integration tests/e2e`
- [x] 3.3 运行 `ruff check .`
- [x] 3.4 运行 `mypy src`
- [x] 3.5 运行 OpenSpec verify、sync 和 archive
