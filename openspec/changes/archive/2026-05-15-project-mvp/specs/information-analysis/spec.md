## ADDED Requirements

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
