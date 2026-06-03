---
capabilities:
  - cap.advisory.trade-advisory
---
# trade-advisory Specification

## Purpose
此规约记录变更 project-mvp 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
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

### Requirement: Historical advice price comparison
系统 SHALL 使用配置的本地价格历史输入，将历史 `Advice` 的 `direction` 与指定 horizon 内的价格移动进行对比，并返回 `aligned`、`diverged` 或 `unknown` verdict。系统 MUST 默认不依赖实时外部市场数据。

#### Scenario: Buy advice aligns with upward price movement
- **WHEN** 一条 `Advice.direction` 为 `buy`，且配置的本地价格历史显示该 `stock_code` 在 advice 数据窗口之后的 horizon 价格相对 baseline 上涨超过阈值
- **THEN** 系统 SHALL 返回 comparison verdict 为 `aligned`，并包含 baseline price、horizon price、实际使用的价格时间和 price_change_percent

#### Scenario: Sell advice diverges from upward price movement
- **WHEN** 一条 `Advice.direction` 为 `sell`，且配置的本地价格历史显示该 `stock_code` 在 advice 数据窗口之后的 horizon 价格相对 baseline 上涨超过阈值
- **THEN** 系统 SHALL 返回 comparison verdict 为 `diverged`，并包含 baseline price、horizon price、实际使用的价格时间和 price_change_percent

#### Scenario: Hold advice aligns with stable price movement
- **WHEN** 一条 `Advice.direction` 为 `hold`，且配置的本地价格历史显示该 `stock_code` 在 advice 数据窗口之后的 horizon 价格变动未超过阈值
- **THEN** 系统 SHALL 返回 comparison verdict 为 `aligned`，并标明该结果来自阈值内价格移动

#### Scenario: Comparison is unknown without local prices
- **WHEN** 未配置价格历史输入，或本地价格历史缺少该 `Advice.stock_code` 的 baseline/horizon 价格
- **THEN** 系统 SHALL 返回 comparison verdict 为 `unknown`，并包含可读的 unknown reason

### Requirement: Deterministic price history input
系统 SHALL 从显式配置的本地 CSV 或 YAML 价格历史输入读取比较数据，MUST 支持测试使用固定 fixture 复现相同 verdict。

#### Scenario: Load configured local price history
- **WHEN** 系统配置包含价格历史输入路径，且文件包含 `stock_code`、timestamp 和 close price
- **THEN** 系统 SHALL 使用该文件计算 advice comparison，不访问外部行情服务

#### Scenario: Reject malformed price history rows
- **WHEN** 本地价格历史输入包含缺少 `stock_code`、timestamp 或 close price 的记录
- **THEN** 系统 MUST 忽略无效记录或返回 `unknown`，并且 MUST 不影响原始 advice 列表和详情展示

