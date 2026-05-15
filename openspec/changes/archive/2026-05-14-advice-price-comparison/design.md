## Context

现有 `Advice` 已包含对比所需的核心字段：`stock_code`、`direction`、`created_at`、`data_window_start`、`data_window_end`。结果浏览已有 `/api/results`、`/api/advices`、`/api/advices/{id}`、`results.html` 和 `advice_detail.html`，能展示建议列表、详情和证据链。

FR43 的关键不是预测行情，而是可复盘：用受控的本地价格历史输入，对历史建议生成可解释、可测试的方向一致性 verdict。

## Goals / Non-Goals

**Goals:**
- 使用本地 CSV/YAML 价格历史输入，保证默认行为 deterministic。
- 为每条 `Advice` 计算 `aligned`、`diverged`、`unknown` verdict。
- 在 API 和 WebUI 复用现有结果浏览模式展示对比结果。
- 保持首版实现小：文本/徽标/表格即可。

**Non-Goals:**
- 不默认调用实时外部市场数据。
- 不实现 K 线、交互图表或技术指标分析。
- 不修改历史 `Advice` 的生成逻辑或审计字段要求。
- 不新增持久化对比结果表；对比结果可按请求由本地价格输入派生。

## Decisions

1. **价格数据来源使用配置指向的本地 fixture/history 文件。**
   - 方案：在系统配置中加入本地价格历史路径、默认 horizon 和最小变动阈值；文件格式首选 CSV，必要时兼容 YAML。
   - 理由：符合不依赖实时外部行情的约束，测试能用固定 fixture。
   - 备选：直接接行情 API。拒绝，默认行为不可重复，也会把 FR43 变成外部集成问题。

2. **comparison 作为派生视图返回，不写入 `Advice`。**
   - 方案：结果浏览查询到 `Advice` 后，根据配置和价格历史生成 comparison 字段。
   - 理由：不需要迁移数据库，避免把可重新计算的快照结果固化到建议审计记录中。
   - 备选：新增 `AdviceComparison` 表。拒绝，首版没有异步批处理或长期审计需求，复杂度不值。

3. **verdict 规则保持机械、透明。**
   - 方案：以 `data_window_end` 后的首个可用价格作为 baseline，取 `baseline + horizon` 附近的可用价格作为 horizon price；涨跌幅超过阈值时判定移动方向。`buy` 对上涨 aligned、下跌 diverged；`sell` 对下跌 aligned、上涨 diverged；`hold` 对阈值内移动 aligned、超阈值移动 diverged；缺少价格或方向无法判定时 unknown。
   - 理由：规则简单，可测试，可解释。
   - 备选：使用 advice `created_at` 作为 baseline。保留为 fallback 更合理，因为 `data_window_end` 更贴近建议所依据的数据窗口。

4. **WebUI 只展示 verdict 和关键字段。**
   - 方案：在建议列表、当前摘要和建议详情中显示 verdict badge、变动百分比、baseline/horizon 时间价格、unknown 原因。
   - 理由：满足复盘需求，不引入图表和前端复杂状态。

## Risks / Trade-offs

- [价格历史文件缺失或覆盖不足] → comparison 返回 `unknown`，WebUI 明示原因，不阻断建议展示。
- [交易日/非交易日导致 horizon 日期无价格] → 使用 horizon 当日或之后的首个可用价格，并在结果中返回实际使用的时间戳。
- [不同市场价格粒度不一致] → 首版只要求按 `stock_code` 和 timestamp 排序的 close price；更复杂字段留给后续。
- [运行时重复解析大文件] → 首版可在请求内解析小 fixture；若后续数据量变大，再引入缓存且保持文件 mtime 失效。

## Migration Plan

1. 新增配置字段时提供安全默认值：未配置价格文件则全部 comparison 为 `unknown`。
2. 现有数据库无需迁移。
3. 回滚时移除配置字段使用和 Web/API comparison 展示，不影响既有 `Advice` 查询。

## Open Questions

- CSV 列名是否固定为 `stock_code,timestamp,close`，还是需要兼容项目已有数据文件格式？首版建议固定列名，减少解析分支。
