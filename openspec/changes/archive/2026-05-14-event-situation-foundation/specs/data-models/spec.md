## ADDED Requirements

### Requirement: EventRecord 数据模型
系统 SHALL 定义 EventRecord 模型存储事件态势记录，MUST 包含 stock_code、title、normalized_keywords、status、heat_score、contradiction、evidence_analysis_ids、evidence_raw_item_ids、source_names、first_seen_at、last_seen_at、created_at 和 updated_at。

#### Scenario: 创建事件记录
- **WHEN** 事件管理能力从归并后的 AnalysisResult 创建新事件
- **THEN** 系统 SHALL 创建 EventRecord，且 evidence_analysis_ids、evidence_raw_item_ids、source_names 和 normalized_keywords 均来自本地 RawItem/AnalysisResult 证据

#### Scenario: 更新事件记录
- **WHEN** 新 AnalysisResult 被归入既有事件
- **THEN** 系统 SHALL 更新 EventRecord 的证据 ID、source_names、last_seen_at、updated_at、contradiction 和 heat_score

### Requirement: EventRecord 状态约束
系统 SHALL 将 EventRecord.status 限定为 discovered、verifying、monitoring、climax、fading 或 archived，MUST 拒绝其他状态值。

#### Scenario: 接受合法状态
- **WHEN** 事件记录状态为 discovered、verifying、monitoring、climax、fading 或 archived 之一
- **THEN** 系统 SHALL 保存该事件记录

#### Scenario: 拒绝非法状态
- **WHEN** 事件记录状态不是 discovered、verifying、monitoring、climax、fading 或 archived
- **THEN** 系统 MUST 拒绝保存该事件记录

### Requirement: EventRecord 证据可追溯性
系统 SHALL 保证 EventRecord 可追溯到关联 RawItem 和 AnalysisResult，MUST 不保存没有本地证据 ID 的正式事件记录。

#### Scenario: 查询事件证据
- **WHEN** 系统查询一条 EventRecord 的证据
- **THEN** 系统 SHALL 返回关联 AnalysisResult 的 summary、sentiment、source_quote、source_url 和关联 RawItem 的 title、url、source_name、published_at

#### Scenario: 阻断无证据事件
- **WHEN** 事件记录缺少 evidence_analysis_ids 或 evidence_raw_item_ids
- **THEN** 系统 MUST 不将其作为正式事件记录保存
