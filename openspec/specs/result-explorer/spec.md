## ADDED Requirements

### Requirement: Latest briefing display
系统 SHALL 展示最近一次生成的简报内容、cycle_id、创建时间和元数据。

#### Scenario: View latest briefing
- **WHEN** 用户打开结果浏览首页
- **THEN** 系统 SHALL 显示最新 `Briefing` 的正文、cycle_id、created_at 和 metadata

#### Scenario: No briefing exists
- **WHEN** 数据库中没有任何 `Briefing`
- **THEN** 系统 SHALL 显示空状态，而不是返回错误页面

### Requirement: Advice list display
系统 SHALL 展示交易建议列表，包含标的、方向、置信度、原因、低置信度标记和创建时间。

#### Scenario: View advice list
- **WHEN** 用户打开建议列表
- **THEN** 系统 SHALL 按 created_at 倒序展示 `Advice` 记录

### Requirement: Evidence chain display
系统 SHALL 支持从建议查看相关分析和原文 URL。

#### Scenario: View advice evidence
- **WHEN** 用户打开一条建议详情
- **THEN** 系统 SHALL 展示该建议的 source_quotes、source_urls，并关联展示匹配的 `AnalysisResult` 与 `RawItem`

### Requirement: Failure source display
系统 SHALL 展示简报 metadata 中记录的失败源信息。

#### Scenario: View failed sources
- **WHEN** 最新简报 metadata 包含 failed_sources
- **THEN** 系统 SHALL 在结果页面展示失败源名称和失败原因
