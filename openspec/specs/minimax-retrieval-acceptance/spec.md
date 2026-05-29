# minimax-retrieval-acceptance Specification

## Purpose
定义 MiniMax 官方公开文档信息获取验收，覆盖配置、采集解析、默认管道产物和 Web API 证据链展示。
## Requirements
### Requirement: MiniMax public documentation source
系统 SHALL 将 MiniMax 官方公开文档配置为可采集的 `web` 信息源，用于无凭据的信息获取验收。

#### Scenario: MiniMax source configured
- **WHEN** 系统加载 `config/portfolio.yaml`
- **THEN** portfolio SHALL 包含名为 `minimax-docs` 的 `web` source，URL 指向 MiniMax 官方文档域名

### Requirement: MiniMax documentation extraction
系统 SHALL 从 MiniMax 文档 HTML 中提取可追溯信息，生成包含 source URL 的 `RawItem`。

#### Scenario: Parse MiniMax documentation fixture
- **WHEN** `parse_web` 使用 `minimax-docs` 的 regex 解析 MiniMax 文档 fixture
- **THEN** 系统 SHALL 生成 `RawItem`，其 title 或 content 包含 MiniMax API 关键信息，source_url 保持为官方文档 URL

### Requirement: MiniMax retrieval evidence
系统 SHALL 通过默认 DAG 验证 MiniMax 来源内容可进入分析、建议、简报和通知产物。

#### Scenario: MiniMax fixture completes DAG workflow
- **WHEN** 默认 DAG 使用 MiniMax fixture 作为 `web-scraper` 输出
- **THEN** 系统 SHALL 生成包含 MiniMax 来源 URL 的 `AnalysisResult` 和 `Advice`

### Requirement: MiniMax evidence visible through Web API
系统 SHALL 通过 Web API 暴露 MiniMax 来源建议的证据链。

#### Scenario: View MiniMax advice evidence
- **WHEN** 用户请求 MiniMax 来源建议详情
- **THEN** API SHALL 返回该建议、关联 `AnalysisResult` 和 `RawItem`，并包含 MiniMax 官方文档 URL
