## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Web disclaimer display
系统 SHALL 在 Web 结果浏览界面持续展示“仅供学习参考，不构成投资建议”声明。

#### Scenario: View results disclaimer
- **WHEN** 用户打开结果浏览首页
- **THEN** 系统 SHALL 显示“不构成投资建议”免责声明
