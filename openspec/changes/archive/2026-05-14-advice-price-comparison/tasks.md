## 1. 价格历史配置与解析

- [x] 1.1 在系统配置 schema 中加入本地价格历史路径、默认 horizon 和最小变动阈值，未配置时保持兼容默认值
- [x] 1.2 实现本地 CSV/YAML 价格历史读取，支持固定 fixture 的 `stock_code`、timestamp、close price
- [x] 1.3 为缺失文件、缺失标的、无效记录和空数据定义 `unknown` 返回路径

## 2. Comparison 计算

- [x] 2.1 实现基于 `Advice.stock_code`、`direction`、`data_window_end`、`created_at` fallback 和 horizon 的 comparison 计算
- [x] 2.2 覆盖 `buy`、`sell`、`hold` 的 `aligned`、`diverged`、`unknown` 单元测试
- [x] 2.3 确保 comparison 作为派生结果返回，不修改 `Advice` 表结构和存量记录

## 3. 结果浏览 API

- [x] 3.1 扩展 `/api/results` 和 `/api/advices`，在 advice payload 中包含 comparison 字段
- [x] 3.2 扩展 `/api/advices/{id}`，在详情 payload 中包含 comparison 且保留证据链字段
- [x] 3.3 增加集成测试覆盖 comparison 字段、unknown fallback 和既有过滤行为兼容

## 4. WebUI

- [x] 4.1 在 `results.html` 当前摘要和建议表格中展示 comparison verdict 与关键变动字段
- [x] 4.2 在 `advice_detail.html` 中展示 comparison 详情和 unknown reason
- [x] 4.3 复用现有样式模式增加非纯颜色依赖的 `aligned`、`diverged`、`unknown` 标签

## 5. 验证

- [x] 5.1 运行相关 unit/integration 测试
- [x] 5.2 运行 `ruff check .`
- [x] 5.3 运行 `mypy src`
- [x] 5.4 运行 `openspec validate advice-price-comparison --type change --json`
