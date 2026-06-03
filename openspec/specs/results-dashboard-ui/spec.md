---
capabilities:
  - cap.web.result-explorer
---
# results-dashboard-ui Specification

## Purpose
此规约记录变更 frontend-react-spa 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Results summary cards
系统 SHALL 以卡片形式展示最新建议摘要，包含方向标签、置信度和复盘结果。

#### Scenario: Display advice summary cards
- **WHEN** 用户进入结果页面
- **THEN** 系统 SHALL 展示最新建议的摘要卡片列表，每张卡片包含标的代码、方向（买入/卖出/持有）、置信度和复盘状态

### Requirement: Briefing display
系统 SHALL 展示最新简报内容和历史简报列表。

#### Scenario: View latest briefing
- **WHEN** 用户进入结果页面
- **THEN** 系统 SHALL 展示最新简报的 run_id、创建时间和内容

#### Scenario: Navigate to briefing detail
- **WHEN** 用户点击历史简报列表中的某条记录
- **THEN** 系统 SHALL 导航到该简报的详情页面

### Requirement: Advice table with filters
系统 SHALL 以表格形式展示建议列表，支持按标的和方向筛选。

#### Scenario: Filter advices by stock code
- **WHEN** 用户在筛选栏输入标的代码
- **THEN** 系统 SHALL 仅展示匹配该标的的建议记录

#### Scenario: Navigate to advice detail
- **WHEN** 用户点击建议表格中的某条记录
- **THEN** 系统 SHALL 导航到该建议的详情页面，展示分析链和原文引用

### Requirement: Event tracking display
系统 SHALL 展示事件追踪表格，包含热度、矛盾标记和证据链。

#### Scenario: View events table
- **WHEN** 用户进入结果页面
- **THEN** 系统 SHALL 展示事件列表，包含标的、标题、状态、热度分数和来源数量

