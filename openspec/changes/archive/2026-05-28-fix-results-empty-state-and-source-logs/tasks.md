## 1. Actions

- [x] A1 更新 `ResultsPage.tsx` 的空数据判定，成功空对象显示明确占位而不是只显示标题。
- [x] A2 在结果首页渲染 `/api/results` 已返回的 `metadata_bar`、`briefings`、`summary_items` 和 `failed_sources`。
- [x] A3 对齐 `SourceLog` 前端类型和信息源页面状态列，统一使用后端返回的 `status` 字段。
- [x] A4 过滤信息源执行日志，默认只返回或展示已配置信息源和 source recovery 记录，排除普通 DAG 节点实例。
- [x] A5 为信息源日志时间列增加 `started_at ?? ended_at` 或明确占位，避免历史 `started_at=null` 造成空白。
- [x] A6 增加或调整前后端测试，覆盖结果空态、结果字段渲染、source log `status` 字段、日志过滤和时间 fallback。

## 2. Checks

- [x] C1 Verify successful empty results show explicit empty state
  - Covers: A1, A6
  - Verifies: `specs/result-explorer/spec.md` / Requirement "Result error state display" / Scenario "Show empty state only after successful empty response"
  - Command: `npm run verify`
  - Expect: `/results` 在 `{briefing:null, briefings:[], advices:[], events:[], summary_items:[]}` 响应下显示当前数据库无可展示结果，且页面标题不是唯一内容

- [x] C2 Verify results summary renders returned fields
  - Covers: A2, A6
  - Verifies: `specs/result-explorer/spec.md` / Requirement "Latest briefing display" / Scenario "View current metadata bar"
  - Command: `npm run verify`
  - Expect: 结果首页展示 `metadata_bar` 中的 cycle_id、数据窗口、失败源数量和免责声明

- [x] C3 Verify briefing history and summary items are visible
  - Covers: A2, A6
  - Verifies: `specs/result-explorer/spec.md` / Requirement "Latest briefing display" / Scenario "View briefing history from results summary"
  - Command: `npm run verify`
  - Expect: `/api/results.briefings` 和 `summary_items` 非空时，结果首页显示对应摘要并保留详情链接

- [x] C4 Verify failed sources render from results API
  - Covers: A2, A6
  - Verifies: `specs/result-explorer/spec.md` / Requirement "Failure source display" / Scenario "View failed sources"
  - Command: `npm run verify`
  - Expect: `/api/results.failed_sources` 非空时，结果页展示失败源名称和原因

- [x] C5 Verify source logs use status field
  - Covers: A3, A6
  - Verifies: `specs/source-health-monitoring/spec.md` / Requirement "Source execution logs" / Scenario "Use status field in source log payload"
  - Command: `npm run verify`
  - Expect: 前端 `SourceLog` 类型和信息源页面读取 `status`，状态列不依赖 `node_status`

- [x] C6 Verify source log UI displays status from backend payload
  - Covers: A3, A6
  - Verifies: `specs/sources-monitor-ui/spec.md` / Requirement "Source execution logs" / Scenario "Display status from status field"
  - Command: `npm run verify`
  - Expect: `/api/sources/health` 或 `/api/sources/logs` 返回 `status` 时，信息源页面状态列显示该值

- [x] C7 Verify ordinary node runs are excluded from source logs
  - Covers: A4, A6
  - Verifies: `specs/source-health-monitoring/spec.md` / Requirement "Source execution logs" / Scenario "Exclude ordinary node runs from source logs"
  - Command: `uv run pytest`
  - Expect: 默认信息源日志查询不返回未配置为信息源的 UUID/普通节点运行记录

- [x] C8 Verify source log time fallback
  - Covers: A5, A6
  - Verifies: `specs/sources-monitor-ui/spec.md` / Requirement "Source execution logs" / Scenario "Display fallback time for source logs"
  - Command: `npm run verify`
  - Expect: `started_at=null` 且 `ended_at` 非空时，信息源日志时间列显示 `ended_at` 或明确占位

## Remediation

- [x] [code_fix] Render `summary_items` created time, low-confidence/degraded state, and direction labels; cover the fields in Playwright.
- [x] [code_fix] Sort merged source recovery and node-run logs by effective timestamp before applying the final limit; cover interleaved timestamps in repository tests.
- [x] [code_fix] Add source selection on the sources page, pass `source_name` to `useSourceLogs`, and cover the filtered query path in Playwright.
