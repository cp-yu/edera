## ADDED Requirements

### Requirement: Event group API display
系统 SHALL 在结果浏览 API 中展示事件组，包含 event id、stock_code、title、status、heat_score、contradiction、source_names、evidence counts、last_seen_at 和 linked evidence。

#### Scenario: List events in results API
- **WHEN** 用户请求 `/api/results`
- **THEN** 系统 SHALL 返回 events 列表，每个 event 包含生命周期状态、热度分数、矛盾标记和关联 AnalysisResult/RawItem 证据摘要

#### Scenario: Filter events by stock code
- **WHEN** 用户请求结果浏览 API 并带有 stock_code 过滤条件
- **THEN** 系统 SHALL 只返回匹配该 stock_code 的事件组，并保持既有 briefing、advice 和 comparison payload 可用

#### Scenario: Event evidence remains linked
- **WHEN** API 返回某个事件组
- **THEN** 系统 SHALL 提供足够字段让客户端追溯到 AnalysisResult.source_quote、AnalysisResult.source_url 和 RawItem.url

### Requirement: Event group WebUI display
系统 SHALL 在本机 Web 结果浏览界面展示事件组、矛盾标记、生命周期状态、热度分数和关联证据，MUST 使用文本、表格和 badge 展示。

#### Scenario: View events on results page
- **WHEN** 用户打开 `/results` 且存在 EventRecord
- **THEN** 系统 SHALL 在结果页面展示事件表格或列表，包含 stock_code、title、status badge、heat_score、contradiction badge、source count、evidence count 和 last_seen_at

#### Scenario: Show contradiction marker
- **WHEN** EventRecord.contradiction=true
- **THEN** WebUI SHALL 使用非纯颜色依赖的文字或 badge 标明“矛盾”，并提供查看双方证据的入口

#### Scenario: Keep UI usable without events
- **WHEN** 数据库中没有任何 EventRecord
- **THEN** 系统 SHALL 保持现有结果页面可用，并显示事件空状态而不是错误页面

### Requirement: Advice detail event context
系统 SHALL 在建议详情页或建议详情 API 中展示与该 Advice 证据相关的事件上下文。

#### Scenario: View related events for advice
- **WHEN** 用户打开 `/results/advices/{id}` 或 `/api/advices/{id}`，且该 Advice.evidence 中的 AnalysisResult 属于 EventRecord
- **THEN** 系统 SHALL 展示相关事件的 title、status、heat_score、contradiction 和 linked evidence

#### Scenario: Advice detail remains usable without event context
- **WHEN** Advice 没有关联 EventRecord
- **THEN** 系统 SHALL 继续展示既有 Advice、AnalysisResult、RawItem 和 comparison 内容
