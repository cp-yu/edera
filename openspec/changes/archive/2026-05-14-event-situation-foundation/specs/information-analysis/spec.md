## ADDED Requirements

### Requirement: 跨源关键词事件归并（FR8）
系统 SHALL 基于 RawItem 和 AnalysisResult 的本地字段执行跨源关键词事件归并，MUST 通过 stock_code、规范化关键词/标题/正文重叠和时间窗口识别同一事件。

#### Scenario: 归并同一事件
- **WHEN** 多条 AnalysisResult 关联的 RawItem 具有相同 stock_code，发布时间落在同一时间窗口内，且 normalized keywords 或标题/摘要 token overlap 达到阈值
- **THEN** 系统 SHALL 将这些 AnalysisResult 归入同一事件组

#### Scenario: 避免跨标的误归并
- **WHEN** 两条 AnalysisResult 的关键词高度相似但 stock_code 不同
- **THEN** 系统 MUST 不将它们归入同一事件组

#### Scenario: 避免过期证据误归并
- **WHEN** 两条 AnalysisResult 的 stock_code 和关键词相似但发布时间超过事件归并时间窗口
- **THEN** 系统 SHALL 创建不同事件组或保持既有事件不变

### Requirement: 跨源矛盾检测（FR10）
系统 SHALL 检测同一事件组内不同来源证据之间的矛盾，MUST 标记事件级 contradiction 并保留矛盾双方 evidence。

#### Scenario: 标记多源矛盾
- **WHEN** 同一事件组内至少两个不同 source_name 或 source_url 的 AnalysisResult 对同一 stock_code 给出相反 sentiment 或明确冲突事实
- **THEN** 系统 SHALL 将事件标记为 contradiction=true，并记录支持双方的 AnalysisResult 和 RawItem 证据

#### Scenario: 同源重复不构成跨源矛盾
- **WHEN** 冲突信号只来自同一 source_name 且没有独立来源佐证
- **THEN** 系统 MUST 不将其作为多源矛盾标记

#### Scenario: 复用 AnalysisResult contradiction 字段
- **WHEN** AnalysisResult 属于已标记 contradiction=true 的事件矛盾证据
- **THEN** 系统 SHALL 允许将该 AnalysisResult.contradiction 置为 true，并保持 source_quote 和 source_url 可查询
