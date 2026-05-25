## 1. Actions

- [x] A1 Add repository support for fetching node output entities by string `entity_id` for briefing and advice detail APIs.
- [x] A2 Normalize backend result payloads from `EntityConfig.attributes` for `/api/results`, `/api/briefings*`, and `/api/advices*`.
- [x] A3 Remove result Web route reads and writes that assume old `Briefing.metadata_` model instances.
- [x] A4 Update frontend result API types and detail route queries to use string ids and `Briefing.metadata`.
- [x] A5 Add explicit error display on the results page so failed `/api/results` requests are not shown as empty data.
- [x] A6 Add focused regression coverage for Entity-backed briefing/advice result payloads and results-page error/empty states.

## 2. Checks

- [x] C1 Verify result APIs handle Entity-backed briefing and advice payloads
  - Covers: A1, A2, A3
  - Command: `uv run pytest tests/core -k "results or briefing or advice"`
  - Expect: `/api/results` and detail APIs return 2xx with flat payloads, `metadata`, and string ids when data is stored in `node_outputs`

- [x] C2 Verify frontend result contracts compile
  - Covers: A4, A5
  - Command: `npx tsc --noEmit`
  - Expect: result pages compile with string route params and `Briefing.metadata`

- [x] C3 Verify full project checks remain green
  - Covers: A1, A2, A3, A4, A5, A6
  - Command: `npm run verify`
  - Expect: existing backend and frontend verification passes without result API regressions

- [x] C4 Verify the original failure no longer renders as empty data
  - Covers: A5, A6
  - Evidence: browser or component-level check of `ResultsPage` with a rejected `/api/results` query
  - Expect: UI shows a loading failure message and does not show “暂无数据”
