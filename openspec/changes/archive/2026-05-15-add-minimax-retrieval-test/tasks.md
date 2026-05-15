## 1. 配置与采集验收

- [x] 1.1 在 `config/portfolio.yaml` 增加 `minimax-docs` Web 信息源
- [x] 1.2 增加 MiniMax 官方文档 fixture
- [x] 1.3 补充配置加载和 `parse_web` 单元测试

## 2. 管道与 Web API 验收

- [x] 2.1 补充默认 DAG 的 MiniMax fixture E2E 测试
- [x] 2.2 补充 Web API 建议详情证据链测试
- [x] 2.3 更新 README，说明 MiniMax 测试边界

## 3. 验证与归档

- [x] 3.1 运行 `pytest tests/unit tests/contract tests/integration tests/e2e`
- [x] 3.2 运行 `ruff check .`
- [x] 3.3 运行 `mypy src`
- [x] 3.4 运行 OpenSpec verify、sync 和 archive
