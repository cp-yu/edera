## Context

当前结果浏览已经有最新简报、建议列表、建议 API 详情和 MiniMax 来源证据链。数据库中 `Briefing`、`Advice`、`AnalysisResult`、`RawItem` 已经持久化，足以支持历史检索和深链详情。PRD 中 FR40、FR41、FR44 可以在不新增模型的前提下先完成基础闭环。

## Goals / Non-Goals

**Goals:**
- 支持历史简报列表、时间过滤和详情查看。
- 支持建议列表按标的、方向、创建时间和数量过滤。
- 支持本机 HTML deep link 打开简报详情和建议证据链。
- 在建议详情中展示 advice、analysis、raw item、source quote 和 source URL。

**Non-Goals:**
- 不做历史建议 vs 股价对比，当前没有行情价格模型。
- 不做 WebSocket、SSE 或自动刷新。
- 不修改通知 payload 或新增 Web base URL 配置。
- 不新增数据库表或 migration。

## Decisions

1. 使用现有表查询实现历史和过滤。

   理由：`Briefing.created_at`、`Advice.stock_code`、`Advice.direction`、`Advice.created_at` 已覆盖本轮查询需求。股票代码过滤简报只能基于 `content` 弱匹配，容易误判，因此本轮只支持简报时间范围过滤。

2. 使用独立 HTML detail routes。

   理由：`/results/briefings/{id}` 和 `/results/advices/{id}` 可以作为稳定深链，适配通知或书签；同时不破坏现有 `/results` 汇总页。

3. API not found 继续使用统一 JSON error。

   理由：现有 API 已用 `error_response()` 返回统一结构，详情接口应保持一致。

## Risks / Trade-offs

- 历史简报无法按标的精确过滤 → 暂不提供该过滤，避免对 `Briefing.content` 做脆弱文本搜索。
- 深链只在本机 WebUI 内有效 → 与当前 `127.0.0.1` 安全边界一致。
- 详情页增加页面数量 → 模板保持简单，复用现有 table/pre/details 样式。
