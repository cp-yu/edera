## 1. Schema 与配置范围

- [x] 1.1 在 `NodeConfig` 中增加最小 `parameters` mapping，并限制为非凭据、JSON-like 可序列化内容
- [x] 1.2 为 reader/advisor/briefing 节点补充必要的 `parameters` 示例或默认空配置
- [x] 1.3 确认 `model`、`timeout_seconds`、`source_names`、`llm_timeout_seconds` 的校验错误会通过现有配置保存路径返回

## 2. Web 入口与保存路径

- [x] 2.1 在配置页面增加分析参数调优入口，展示相关配置来源和白名单参数
- [x] 2.2 复用 `RuntimeConfigEditor.save()` 或等价路径保存分析参数，不新增绕过校验的写文件逻辑
- [x] 2.3 确保通用配置编辑入口仍可编辑 `system`、`portfolio`、`node`、`dag` 和 `skill` 配置
- [x] 2.4 在界面或返回状态中明确保存只影响后续运行，当前运行继续使用启动快照

## 3. 测试

- [x] 3.1 添加 `NodeConfig.parameters` 合法与非法内容的单元测试
- [x] 3.2 添加分析参数入口列表/页面测试，覆盖 reader/advisor/briefing 节点和采集节点 `source_names`
- [x] 3.3 添加保存合法分析参数的 Web/API 测试
- [x] 3.4 添加提交未允许字段或非法 `parameters` 时的拒绝保存测试
- [x] 3.5 添加回归测试，确认通用配置编辑功能未被破坏

## 4. Verification

- [x] 4.1 运行 `pytest`
- [x] 4.2 运行 `ruff check .`
- [x] 4.3 运行 `mypy src`
- [x] 4.4 运行 `openspec validate analysis-parameter-tuning --type change --json`
- [x] 4.5 实现完成后运行 OpenSpec sync/verify 流程
- [x] 4.6 验收完成后归档 `analysis-parameter-tuning`
