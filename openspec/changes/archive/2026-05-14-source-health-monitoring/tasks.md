## 1. 查询聚合

- [x] 1.1 增加信息源健康汇总查询，复用 `PipelineRun`、`NodeRun` 和最新 `Briefing.metadata_.failed_sources`
- [x] 1.2 增加信息源执行日志查询，支持 limit 和按信息源名称过滤
- [x] 1.3 为配置源名称到采集节点的映射补最小实现，并在无法映射时保持节点名可见

## 2. Web/API 展示

- [x] 2.1 增加本机 API 返回信息源健康状态列表
- [x] 2.2 增加本机 API 返回信息源执行日志列表
- [x] 2.3 在 Web 控制台增加信息源健康状态与执行日志入口

## 3. 验证

- [x] 3.1 增加 repository 或服务层测试覆盖成功率、未知状态和失败原因回退
- [x] 3.2 增加 Web API 测试覆盖健康汇总、按源过滤日志和空数据返回
- [x] 3.3 运行相关单元与集成测试，并确认不影响现有管道控制和结果浏览行为
- [x] 3.4 运行 `pytest tests/unit tests/contract tests/integration tests/e2e`
- [x] 3.5 运行 `ruff check .`
- [x] 3.6 运行 `mypy src`
- [x] 3.7 运行 OpenSpec verify、sync 和 archive
