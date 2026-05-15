## Why

当前项目已经完成后台管道和本机 Web 控制台，但主动目标要求以 MiniMax 信息获取作为测试来证明“完整项目，包含 WebUI”。现有配置、代码和测试没有 MiniMax 相关验收路径，无法把该要求追溯到具体证据。

## What Changes

- 新增 MiniMax 官方文档作为公开 Web 信息源的验收配置，不保存 API key，不调用真实 MiniMax 模型接口。
- 用现有 `web` 抓取能力解析 MiniMax 文档页中的 API 关键信息，产出可追溯 `RawItem`。
- 补充测试，证明 MiniMax 信息源可进入默认采集链路，并可通过 Web API 的建议详情看到原文证据链。
- 补充运行说明，明确该测试验证的是公开文档信息获取，不是 MiniMax 付费 API 调用。

## Capabilities

### New Capabilities
- `minimax-retrieval-acceptance`: MiniMax 官方文档信息获取验收，覆盖配置、采集、管道产物和 Web API 证据展示

### Modified Capabilities
- `result-explorer`: Web 结果浏览需要覆盖 MiniMax 来源的建议证据链

## Impact

- **配置**: 更新 `config/portfolio.yaml`，加入 MiniMax 官方文档 Web 源。
- **测试**: 更新采集单元测试、端到端管道测试和 Web API 集成测试。
- **文档**: 更新 `README.md` 的验收说明。
- **依赖/API**: 不新增依赖，不新增公网绑定，不新增真实 MiniMax API 调用。
