# notification-delivery Specification

## Purpose
此规约记录变更 project-mvp 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 分级推送（FR19）
系统 SHALL 通过 ntfy.sh 按优先级分级推送消息，MUST 将优先级映射到 ntfy priority 字段（1=静默, 3=普通, 5=紧急）。

#### Scenario: 紧急推送
- **WHEN** 系统检测到重大事件需要立即行动
- **THEN** 通过 ntfy.sh 发送 priority=5 的推送，手机端呈现为紧急通知

#### Scenario: 常规推送
- **WHEN** 周期简报生成完成，无紧急事件
- **THEN** 通过 ntfy.sh 发送 priority=3 的推送

### Requirement: 推送摘要格式（FR20）
系统 SHALL 输出结构化推送摘要，标题 MUST 不超过 16 字，摘要 MUST 包含标的、方向、核心原因、时间、置信度。

#### Scenario: 常规通知摘要
- **WHEN** 系统推送一条常规通知
- **THEN** 标题 ≤16 字，摘要包含所有必含字段（标的、方向、核心原因、时间、置信度）

#### Scenario: 标题超长截断
- **WHEN** 生成的标题超过 16 字
- **THEN** 系统截断标题至 16 字以内

### Requirement: 高优先级推送行动方向（FR21）
系统 SHALL 在高优先级推送中包含明确的行动方向（买/卖 + 核心原因）。

#### Scenario: 号外推送包含行动方向
- **WHEN** 系统发送 priority=5 的推送
- **THEN** 推送内容包含明确的买入或卖出方向及核心原因

### Requirement: 周期性状态输出（FR22）
系统 SHALL 按固定周期至少推送一次状态结果，MUST 确保用户可感知系统在线状态。

#### Scenario: 周期性推送
- **WHEN** 每 30min 周期完成
- **THEN** 系统至少推送一次结果（简报摘要或系统状态通知）

#### Scenario: 无新信息时仍推送状态
- **WHEN** 当前周期无新采集信息
- **THEN** 系统推送系统状态通知，确认系统正常运行

