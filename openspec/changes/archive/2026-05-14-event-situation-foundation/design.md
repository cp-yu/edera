## Context

`AnalysisResult` 已包含 `keywords`、`sentiment`、`confidence`、`source_quote`、`source_url` 和单条级别的 `contradiction`。结果浏览已经能展示建议、分析链、原文、失败源和本地价格复盘。PRD 的 P2 下一步要求跨源事件归并、矛盾检测、事件生命周期和事件热度；UX 要求矛盾信息在摘要层可见，并能并列查看证据。

约束很明确：本变更只建立事件态势基础，不做预测、不做弱信号建议触发、不做 Node Graph UI、不接实时行情。实现应保持确定性，方便用 fixture 覆盖。

## Goals / Non-Goals

**Goals:**
- 从 RawItem/AnalysisResult 派生事件组，创建或更新持久化事件记录。
- 用简单可解释规则完成跨源归并：`stock_code` + 关键词/标题/正文规范化重叠 + 时间窗口。
- 将跨源矛盾检测落到可查询数据：事件有矛盾标记，矛盾双方证据可见，相关 AnalysisResult 可继续使用 `contradiction`。
- 提供最小事件生命周期状态和确定性 `heat_score`。
- 在现有结果浏览 API/WebUI 中以表格、文本和 badge 展示事件，不引入图形化复杂度。

**Non-Goals:**
- 不实现 FR47 热度拐点预测，只保存后续趋势逻辑需要的热度、证据数量、来源数量、最近证据时间等字段。
- 不实现 FR48 弱信号高置信建议触发。
- 不实现 Node Graph UI、复杂关系图或图表。
- 不接入实时外部市场数据或新第三方服务。
- 不重写现有建议生成链路。

## Decisions

### 1. 事件记录持久化，而不是请求时临时聚合

事件是 P2 后续生命周期、热度、审计和复盘的共同对象，应新增事件记录表，而不是只在 `/api/results` 请求时临时计算。

备选方案是每次查询时按 AnalysisResult 临时聚合。它少一次 migration，但无法可靠保存生命周期、状态变更、归档和未来趋势字段，也难以支持详情深链。

### 2. 首版归并使用确定性本地启发式

归并规则按以下顺序收敛：
- 从 RawItem.stock_codes 和 Advice/AnalysisResult 证据上下文确定 `stock_code`。
- 对 AnalysisResult.keywords、RawItem.title、RawItem.content 做规范化：大小写折叠、全半角/空白规整、常见标点剔除、关键词去重。
- 候选事件必须同 `stock_code`，且证据时间落在配置或默认时间窗口内。
- 满足关键词 overlap 阈值，或标题/摘要 token overlap 阈值时归入同一事件。
- 不满足阈值时创建新事件。

备选方案是用 LLM 判断事件同一性。它更灵活，但不可复现、难测试，并会把 P2 基础能力绑到模型质量上。首版应先用可审计规则。

### 3. 矛盾检测基于事件内多源信号冲突

跨源矛盾的最小定义：同一事件内存在来自不同 source_name/source_url 的证据，对同一 stock_code 给出相反 sentiment，或明确命中相互冲突的关键词/摘要事实。事件记录保存 `contradiction=true` 和冲突证据引用；相关 AnalysisResult 的 `contradiction` 可被更新为 true。

备选方案是保留现有单条 `AnalysisResult.contradiction`。这不能满足 PRD/UX 的“多源信息间矛盾”和“双方证据并列展示”，所以必须提升到事件级。

### 4. 生命周期由证据和用户/系统动作驱动，首版只做最小状态机

允许状态集合固定为 `discovered`、`verifying`、`monitoring`、`climax`、`fading`、`archived`。默认规则：
- 新事件为 `discovered`。
- 多来源或矛盾证据进入 `verifying`。
- 持续新增证据进入 `monitoring`。
- `heat_score` 达到阈值进入 `climax`。
- 新近证据不足且热度下降进入 `fading`。
- 超过保留窗口或显式归档进入 `archived`。

首版不要求复杂状态历史表，但事件记录必须保存状态和更新时间；如实现成本很小，可增加状态历史字段供后续审计扩展。

### 5. 热度分数只使用本地证据

`heat_score` 使用确定性公式，例如：

`heat_score = evidence_count_weight + source_diversity_weight + recency_weight + contradiction_weight`

输入只来自本地事件证据：证据条数、独立来源数量、最近证据时间、是否矛盾。分数应被夹在固定范围内，例如 0-100，并返回组成字段，便于测试和 UI 解释。

备选方案是加入价格/成交量/外部热搜。它超出本变更范围，也会破坏无第三方依赖和 fixture 可复现。

### 6. Result Explorer 用现有朴素页面形态扩展

结果浏览保持当前 server-rendered HTML 和 JSON API 风格。首页增加事件组表格或摘要块；建议详情展示相关事件及证据；API payload 包含事件 `id`、`stock_code`、`title`、`status`、`heat_score`、`contradiction`、`evidence` 和 `updated_at`。

不引入 Node Graph、关系图或折线图。文本、表格、badge 已足够验证 P2 事件基础。

## Risks / Trade-offs

- [误归并] → 阈值保守，要求同 `stock_code` 和时间窗口；测试覆盖同标的不同事件、不同标的同关键词。
- [漏归并] → 保存 normalized keywords 和 evidence，允许后续规则迭代重新更新事件。
- [矛盾误报] → 首版只对不同来源的相反 sentiment 或明确冲突事实标记跨源矛盾，避免同一来源重复造成误报。
- [热度分数被误解为行情信号] → API/WebUI 标明它是本地证据热度，不包含实时市场数据。
- [迁移影响现有数据] → 新表和可空/派生字段优先，现有 Advice/Briefing 查询不应因没有事件数据失败。
