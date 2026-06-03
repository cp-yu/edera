---
capabilities:
  - cap.advisory.trade-advisory
---
# information-analysis Specification

## Purpose
定义 摘要与关键词生成（FR7）、利好/利空分类（FR7）、原文引用与 URL 溯源（FR11）、跨源关键词事件归并（FR8）等能力。
## Requirements
### Requirement: 摘要与关键词生成（FR7）
系统 SHALL 对每条 RawItem 生成摘要和提取关键词，摘要 MUST 保留原文核心信息，不引入 LLM 幻觉内容。

#### Scenario: 成功生成摘要
- **WHEN** summarize Skill 接收一条 RawItem
- **THEN** 返回包含 summary（≤200字）和 keywords（≤10个）的结构化输出

### Requirement: 利好/利空分类（FR7）
系统 SHALL 对每条信息标注利好(bullish)/利空(bearish)/中性(neutral)分类，MUST 附带分类依据。

#### Scenario: 明确利好信息
- **WHEN** classify-sentiment Skill 分析一条包含明确正面信号的信息
- **THEN** 返回 sentiment=bullish，附带分类依据引用

#### Scenario: 矛盾信息分类
- **WHEN** 单条信息中同时包含正面和负面信号
- **THEN** 返回 sentiment 标注及矛盾标记，附带双方信号引用

### Requirement: 原文引用与 URL 溯源（FR11）
系统 SHALL 为每条分析结果关联原文引用片段和原始 URL，MUST 确保溯源链完整。

#### Scenario: 分析结果包含溯源
- **WHEN** 分析节点完成一条信息的分析
- **THEN** AnalysisResult 包含 source_quote（原文引用）和 source_url（原始 URL），均非空

#### Scenario: 溯源字段校验
- **WHEN** 分析结果缺少 source_quote 或 source_url
- **THEN** 系统拒绝该分析结果进入后续管道

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
