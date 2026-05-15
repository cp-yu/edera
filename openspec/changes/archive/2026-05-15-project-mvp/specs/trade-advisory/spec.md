## ADDED Requirements

### Requirement: 生成交易建议（FR15）
系统 SHALL 基于当期采集的分析结果与用户当前投资情况生成交易建议，输出 MUST 包含 direction（buy/sell/hold）和核心原因。

#### Scenario: 生成买入建议
- **WHEN** generate-advice Skill 接收某标的的多条利好分析结果，用户当前未持有该标的
- **THEN** 返回 direction=buy 的建议，附带核心原因和置信度

#### Scenario: 生成持有建议
- **WHEN** 某标的无显著新信息
- **THEN** 返回 direction=hold 的建议，注明无新增信息

#### Scenario: 综合用户投资情况
- **WHEN** 用户已重仓某标的，该标的出现利空信号
- **THEN** 建议中考虑用户持仓权重，可能提高卖出建议的优先级

### Requirement: 建议原文溯源（FR18）
系统 SHALL 为每条建议附带原文引用和原始 URL 溯源，MUST 确保从建议可回溯到所有支撑该建议的原始信息。

#### Scenario: 建议包含完整证据链
- **WHEN** 建议节点生成一条交易建议
- **THEN** Advice 记录包含 source_quotes（原文引用列表）和 source_urls（URL 列表），均非空

#### Scenario: 证据不足阻断
- **WHEN** 建议缺少必要来源证据（无 source_quote 或无 source_url）
- **THEN** 系统不输出该条为正式建议

### Requirement: 审计字段完整性
系统 MUST 确保每条 Advice 包含完整审计字段：标的、时间、方向、核心原因、置信度、原文来源 URL、原文引用片段、投资情况快照。

#### Scenario: 审计字段校验
- **WHEN** 建议生成后进行审计字段校验
- **THEN** 所有必填审计字段均有值，缺失任一字段时不进入正式留存

### Requirement: 低置信度标记
系统 SHALL 允许输出低置信度建议，MUST 明确标记"低置信度"状态。

#### Scenario: 低置信度建议输出
- **WHEN** 支撑建议的证据有限或信号不明确
- **THEN** 建议仍可输出，但 confidence 字段值低且附带低置信度标记
