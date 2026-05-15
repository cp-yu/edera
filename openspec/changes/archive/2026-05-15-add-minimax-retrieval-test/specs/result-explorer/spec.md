## MODIFIED Requirements

### Requirement: Evidence chain display
系统 SHALL 支持从建议查看相关分析和原文 URL，并覆盖 MiniMax 官方文档来源的建议证据链。

#### Scenario: View advice evidence
- **WHEN** 用户打开一条建议详情
- **THEN** 系统 SHALL 展示该建议的 source_quotes、source_urls，并关联展示匹配的 `AnalysisResult` 与 `RawItem`

#### Scenario: View MiniMax source evidence
- **WHEN** 用户打开一条基于 `minimax-docs` 来源生成的建议详情
- **THEN** 系统 SHALL 返回包含 MiniMax 官方文档 URL 的 `source_urls`、`AnalysisResult.source_url` 和 `RawItem.url`
