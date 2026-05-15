## 1. 摘要数据派生

- [x] 1.1 在 Web 路由层派生当前 metadata bar 字段
- [x] 1.2 在 Web 路由层派生建议摘要状态字段

## 2. 结果页 UI

- [x] 2.1 更新结果页模板，增加 metadata bar 和免责声明
- [x] 2.2 将建议列表升级为当前摘要列表，保留过滤和详情链接
- [x] 2.3 增加方向、低置信度和降级状态 CSS

## 3. 验证与归档

- [x] 3.1 补充 Web 集成测试覆盖 metadata bar、免责声明和摘要语义状态
- [x] 3.2 运行 `pytest tests/unit tests/contract tests/integration tests/e2e`
- [x] 3.3 运行 `ruff check .`
- [x] 3.4 运行 `mypy src`
- [x] 3.5 运行 OpenSpec verify、sync 和 archive
