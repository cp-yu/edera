## ADDED Requirements

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
