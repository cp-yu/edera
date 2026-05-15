## Context

项目现有采集层已经支持 `rss` 和 `web` 两类公开源，Web 控制台也已提供结果、证据链、管道控制和配置编辑。缺口不是再造一套 MiniMax SDK，而是把“MiniMax 信息获取”落成可重复、无凭据、可测试的验收路径。

官方文档证据显示 MiniMax 文本接口使用 Bearer Auth、`application/json` 请求体、OpenAI-compatible chat 接口和 `MiniMax-M2.x` 系列模型。该信息可以从公开文档页获取，适合作为非标准公开源采集测试。

## Goals / Non-Goals

**Goals:**
- 使用 MiniMax 官方文档页验证现有 `web` 源抓取和正则结构化能力。
- 让 MiniMax 来源的内容进入默认 DAG，生成分析、建议、简报和通知 payload。
- 通过 Web API 建议详情证明 MiniMax 原文 URL 与 `RawItem` 可追溯。

**Non-Goals:**
- 不实现 MiniMax API 客户端。
- 不提交 API key、base URL 凭据或真实模型调用配置。
- 不重构采集、分析、建议或 WebUI 架构。

## Decisions

1. 使用 `web` 源而不是新增 `minimax` source type。

   理由：MiniMax 官方文档是公开 HTML 页面，现有 `web` 源已经覆盖“URL + regex”结构化抓取。新增 source type 只会扩大配置 schema、DAG 和 handler 分支，当前验收不需要。

   备选方案：新增专用 MiniMax adapter。该方案适合真实 API 调用或 SDK 集成，但会引入凭据、安全和网络不确定性，不适合当前测试闭环。

2. 测试使用 fixture HTML，不在测试中访问公网。

   理由：验收应该稳定、快速、可离线。fixture 保留官方文档关键信息，单元测试负责证明解析规则，E2E 负责证明管道集成。

3. WebUI 验收走现有 API。

   理由：`/api/advices/{id}` 已经返回 `Advice`、`AnalysisResult` 和 `RawItem`。只需补测试证明 MiniMax 来源证据链可见，不需要新增页面或路由。

## Risks / Trade-offs

- 官方文档 HTML 结构变化 → 正则配置可能失效；测试 fixture 会捕捉规则意图，真实运行失败会进入现有失败源展示。
- 不调用真实 MiniMax API → 只能证明公开文档信息获取，不证明模型推理能力；该边界会写入 README。
- 使用通用 `web` 源 → 对复杂页面解析能力有限；当前仅验证公开文档关键信息，保持实现简单。
