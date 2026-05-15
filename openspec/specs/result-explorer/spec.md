## Purpose

定义本机 Web 控制台的结果浏览能力，包括最新简报、建议列表、建议详情证据链、失败源展示，以及外部公开源进入管道后的可追溯证据查看。
## Requirements
### Requirement: Latest briefing display
系统 SHALL 展示最近一次生成的简报内容、cycle_id、创建时间和元数据，并提供进入历史简报列表和简报详情的入口。结果浏览首页还 SHALL 展示当前周期 metadata bar，包含 cycle_id、created_at、数据时间窗口、失败源数量和免责声明。

#### Scenario: View latest briefing
- **WHEN** 用户打开结果浏览首页
- **THEN** 系统 SHALL 显示最新 `Briefing` 的正文、cycle_id、created_at 和 metadata

#### Scenario: No briefing exists
- **WHEN** 数据库中没有任何 `Briefing`
- **THEN** 系统 SHALL 显示空状态，而不是返回错误页面

#### Scenario: View current metadata bar
- **WHEN** 用户打开结果浏览首页且存在最新 `Briefing`
- **THEN** 系统 SHALL 显示 cycle_id、created_at、数据时间窗口、失败源数量和“不构成投资建议”免责声明

### Requirement: Advice list display
系统 SHALL 展示交易建议列表，包含标的、方向、置信度、原因、低置信度标记和创建时间，并支持按 `stock_code`、`direction`、created_at 时间范围和 limit 过滤。结果浏览首页还 SHALL 将建议作为当前摘要列表展示，并在摘要层用文本和样式区分 `buy`、`sell`、`hold`、低置信度和采集降级状态。

#### Scenario: View advice list
- **WHEN** 用户打开建议列表
- **THEN** 系统 SHALL 按 created_at 倒序展示 `Advice` 记录

#### Scenario: Filter advice list
- **WHEN** 用户请求带 `stock_code`、`direction` 或时间范围的建议列表
- **THEN** 系统 SHALL 仅返回匹配条件的 `Advice` 记录，并保持 created_at 倒序

#### Scenario: Scan current summary
- **WHEN** 用户打开结果浏览首页且存在建议
- **THEN** 系统 SHALL 显示每条建议的标的、方向、置信度、核心原因、创建时间、低置信度标记和详情链接

#### Scenario: Show semantic summary state
- **WHEN** 建议方向为 `buy`、`sell`、`hold` 或 `low_confidence=true`
- **THEN** 系统 SHALL 在摘要层展示对应文字标签和非纯颜色依赖的状态样式

### Requirement: Evidence chain display
系统 SHALL 支持从建议查看相关分析和原文 URL，并覆盖 MiniMax 官方文档来源的建议证据链。

#### Scenario: View advice evidence
- **WHEN** 用户打开一条建议详情
- **THEN** 系统 SHALL 展示该建议的 source_quotes、source_urls，并关联展示匹配的 `AnalysisResult` 与 `RawItem`

#### Scenario: View MiniMax source evidence
- **WHEN** 用户打开一条基于 `minimax-docs` 来源生成的建议详情
- **THEN** 系统 SHALL 返回包含 MiniMax 官方文档 URL 的 `source_urls`、`AnalysisResult.source_url` 和 `RawItem.url`

### Requirement: Failure source display
系统 SHALL 展示简报 metadata 中记录的失败源信息。

#### Scenario: View failed sources
- **WHEN** 最新简报 metadata 包含 failed_sources
- **THEN** 系统 SHALL 在结果页面展示失败源名称和失败原因

### Requirement: Briefing history search
系统 SHALL 提供历史简报列表，按 created_at 倒序返回，并支持 created_at 起止时间和 limit 过滤。

#### Scenario: List briefing history
- **WHEN** 用户请求历史简报列表
- **THEN** 系统 SHALL 返回按 created_at 倒序排列的 `Briefing` 记录

#### Scenario: Filter briefing history by time
- **WHEN** 用户请求带 created_at 起止时间的历史简报列表
- **THEN** 系统 SHALL 只返回时间范围内的 `Briefing` 记录

### Requirement: Result deep links
系统 SHALL 提供稳定的本机 HTML 和 API 深链，允许用户直达单条简报或单条建议证据链。

#### Scenario: Open briefing deep link
- **WHEN** 用户访问 `/results/briefings/{id}` 或 `/api/briefings/{id}`
- **THEN** 系统 SHALL 返回对应 `Briefing`；不存在时 API MUST 返回统一 JSON error，HTML SHALL 返回不崩溃的未找到页面

#### Scenario: Open advice deep link
- **WHEN** 用户访问 `/results/advices/{id}` 或 `/api/advices/{id}`
- **THEN** 系统 SHALL 返回对应 `Advice`、相关 `AnalysisResult` 和 `RawItem`；不存在时 API MUST 返回统一 JSON error，HTML SHALL 返回不崩溃的未找到页面

### Requirement: Web disclaimer display
系统 SHALL 在 Web 结果浏览界面持续展示“仅供学习参考，不构成投资建议”声明。

#### Scenario: View results disclaimer
- **WHEN** 用户打开结果浏览首页
- **THEN** 系统 SHALL 显示“不构成投资建议”免责声明

### Requirement: Result auto refresh
系统 SHALL 在结果浏览首页自动检测最新 `Briefing` 版本，并在新结果到达时刷新页面以展示新结果。

#### Scenario: Refresh when latest briefing changes
- **WHEN** 用户打开结果浏览首页且之后 `GET /api/briefings/latest` 返回的 `Briefing.id` 或 `created_at` 与页面初始版本不同
- **THEN** 系统 SHALL 自动刷新当前结果浏览页面，并保留当前 URL 查询参数

#### Scenario: Keep empty state while waiting for first briefing
- **WHEN** 用户打开结果浏览首页且数据库中没有任何 `Briefing`
- **THEN** 系统 SHALL 显示既有空状态，并继续检测直到新 `Briefing` 到达

#### Scenario: Tolerate refresh check failure
- **WHEN** 自动刷新检查请求失败或返回非 2xx 响应
- **THEN** 系统 MUST 保持当前页面内容可用，并在后续检查周期继续检测

### Requirement: Advice comparison API display
系统 SHALL 在结果浏览 API 中为建议记录展示基于本地价格历史计算的 comparison 字段，覆盖列表、结果摘要和建议详情。

#### Scenario: List advices with comparison
- **WHEN** 用户请求 `/api/advices` 或 `/api/results`
- **THEN** 系统 SHALL 在每条 advice payload 中包含 comparison verdict、horizon、baseline price、horizon price、price_change_percent 和 unknown reason

#### Scenario: Open advice detail with comparison
- **WHEN** 用户请求 `/api/advices/{id}`
- **THEN** 系统 SHALL 返回该建议的 comparison 字段，并保持既有 `Advice`、`AnalysisResult` 和 `RawItem` 证据链字段可用

### Requirement: Advice comparison WebUI display
系统 SHALL 在本机 Web 结果浏览界面展示建议价格对比 verdict，让用户能从建议列表和建议详情复盘历史建议与价格移动的关系。

#### Scenario: View comparison in results page
- **WHEN** 用户打开 `/results` 且建议存在
- **THEN** 系统 SHALL 在当前摘要和建议表格中显示每条建议的 comparison verdict，并用非纯颜色依赖的文本标签区分 `aligned`、`diverged` 和 `unknown`

#### Scenario: View comparison in advice detail page
- **WHEN** 用户打开 `/results/advices/{id}`
- **THEN** 系统 SHALL 展示该建议的 comparison verdict、baseline price、horizon price、price_change_percent、horizon 和 unknown reason

#### Scenario: Keep WebUI usable when comparison is unknown
- **WHEN** comparison verdict 为 `unknown`
- **THEN** 系统 SHALL 继续展示 advice 内容和证据链，并在 comparison 区域显示 unknown reason

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

