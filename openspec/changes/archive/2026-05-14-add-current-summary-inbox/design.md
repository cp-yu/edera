## Context

现有 `result-explorer` 已能展示最新简报、建议列表、历史简报和建议详情证据链。UX 规格要求的 Inbox 首屏可以先用现有 `Advice`、`Briefing.metadata_` 和 `source_urls` 派生，不需要新表，也不需要前端框架。

## Goals / Non-Goals

**Goals:**
- 在 `/results` 首屏提供可扫描的当前建议摘要列表。
- 展示 metadata bar：cycle、创建时间、数据窗口、失败源数量和免责声明。
- 在摘要层暴露方向、置信度、低置信度和失败源降级状态。
- 保持现有表格、过滤、历史简报和详情链接可用。

**Non-Goals:**
- 不实现已读/未读持久化。
- 不实现 WebSocket、SSE 或自动刷新。
- 不引入行情数据或建议 vs 股价对比。
- 不迁移到 SPA 或引入新 UI 依赖。

## Decisions

1. 使用服务端派生的 summary view model。

   理由：现有 Jinja 页面已经由 `_result_summary()` 聚合数据。把 metadata 和 advice 状态在路由层派生，可避免模板内堆积判断，也不改变持久化模型。

2. 当前摘要以 `Advice` 为列表主体。

   理由：PRD 的首屏摘要需要标的、方向、核心原因和置信度，`Advice` 已具备这些字段。`Briefing` 保持作为右侧或下方详情入口，不强行解析简报正文。

3. 使用 CSS 类表达语义状态。

   理由：买/卖/持有、低置信度和降级状态是展示语义，不应污染数据模型。CSS 类可在不引入组件库的前提下实现清晰状态表达。

## Risks / Trade-offs

- 摘要列表不是完整双栏 Inbox → 本轮先完成当前周期摘要和元数据，避免一次性重做整个 UI。
- `Advice` 与 `Briefing` 没有显式 cycle 外键 → 当前摘要仍沿用最近 advice 列表；仅 metadata bar 使用最新 briefing 的 cycle。
- 免责声明重复展示可能显得啰嗦 → 用页面底部或 metadata bar 的短文本固定呈现，满足 FR46 边界控制。
