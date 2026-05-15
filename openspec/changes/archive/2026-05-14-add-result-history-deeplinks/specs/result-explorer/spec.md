## MODIFIED Requirements

### Requirement: Latest briefing display
系统 SHALL 展示最近一次生成的简报内容、cycle_id、创建时间和元数据，并提供进入历史简报列表和简报详情的入口。

#### Scenario: View latest briefing
- **WHEN** 用户打开结果浏览首页
- **THEN** 系统 SHALL 显示最新 `Briefing` 的正文、cycle_id、created_at 和 metadata

#### Scenario: No briefing exists
- **WHEN** 数据库中没有任何 `Briefing`
- **THEN** 系统 SHALL 显示空状态，而不是返回错误页面

### Requirement: Advice list display
系统 SHALL 展示交易建议列表，包含标的、方向、置信度、原因、低置信度标记和创建时间，并支持按 `stock_code`、`direction`、created_at 时间范围和 limit 过滤。

#### Scenario: View advice list
- **WHEN** 用户打开建议列表
- **THEN** 系统 SHALL 按 created_at 倒序展示 `Advice` 记录

#### Scenario: Filter advice list
- **WHEN** 用户请求带 `stock_code`、`direction` 或时间范围的建议列表
- **THEN** 系统 SHALL 仅返回匹配条件的 `Advice` 记录，并保持 created_at 倒序

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

## ADDED Requirements

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
