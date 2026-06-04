### Task 1: 执行摘要日志

**Goal**: 为每个实际执行过的节点生成系统 execution summary log，同时保持业务 output 语义不变。

**Files**:
- Modify: `packages/core/src/edera_core/node/executor.py`
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `tests/core/unit/test_node_executor.py`
- Test: `tests/core/integration/test_dag_runner.py`

**Requirements**:
- 实际执行成功且有 payload 时记录 summary log，并保留业务 output 写入。
- 实际执行成功但 payload 为空时记录 summary log，不伪造业务 output。
- 实际执行失败时记录 summary log，不把失败摘要写入 `node_outputs`。
- 未启动执行的 `upstream_failed` 节点不要求 summary log。

#### Checks

- [x] C1 Verify successful executed node summary
  - Verifies: `specs/dag-run-observability/spec.md` / Requirement "Executed node execution logs" / Scenario "Successful node with payload records log"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py`
  - Expect: 成功 handler 测试证明业务 output 与 execution summary log 都被记录

- [x] C2 Verify empty payload summary without output entity
  - Verifies: `specs/dag-run-observability/spec.md` / Requirement "Executed node execution logs" / Scenario "Successful node without payload records log"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py`
  - Expect: 空 payload 成功节点有 summary log，且没有为可观测性创建业务 `NodeOutputEntity`

- [x] C3 Verify failed executed node summary and unstarted exclusion
  - Verifies: `specs/dag-run-observability/spec.md` / Requirement "Executed node execution logs" / Scenario "Failed executed node records log", Scenario "Unstarted node has no required log"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py tests/core/integration/test_dag_runner.py`
  - Expect: 执行失败节点有 summary log；`upstream_failed` 未执行节点不被要求写 summary log

### Task 2: 日志索引与持久化

**Goal**: 让 execution summary log 和 raw process log 都能通过 DB-backed log index 查询。

**Files**:
- Modify: `packages/core/src/edera_core/storage/entities.py`
- Modify: `packages/core/src/edera_core/storage/database.py`
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `tests/core/unit/test_node_executor.py`

**Requirements**:
- `log_index` 能区分 summary log 与 raw process log。
- summary log 以小型结构化日志保存并索引。
- raw stdout/stderr 继续落文件并索引。
- 完整日志内容不写入 runtime facts 表或 `node_outputs`。

#### Checks

- [x] C4 Verify execution summary log indexing
  - Verifies: `specs/dag-run-observability/spec.md` / Requirement "Execution log storage boundary" / Scenario "Execution summary log indexed"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py`
  - Expect: 测试可查询到带 `run_id`、`node_id`、log kind、path、size、digest 的 summary log index

- [x] C5 Verify raw log indexing and storage boundary
  - Verifies: `specs/dag-run-observability/spec.md` / Requirement "Execution log storage boundary" / Scenario "Raw process log indexed", Scenario "Logs stay out of runtime facts and outputs"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py`
  - Expect: raw stdout/stderr 文件被索引，完整日志内容没有写入 runtime facts 表或 `node_outputs`

### Task 3: Agent 日志一致性

**Goal**: 让 agent 节点成功、失败、无 stdout 三种情况都能通过历史日志查询解释执行结果。

**Files**:
- Modify: `packages/core/src/edera_core/node/executor.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `tests/core/unit/test_node_executor.py`
- Test: `tests/core/unit/test_core_architecture_overhaul.py`

**Requirements**:
- agent stdout 继续实时推送。
- agent raw stdout log 继续落文件并索引。
- agent 成功和失败都记录 execution summary。
- agent 无 stdout 时仍记录 execution summary。

#### Checks

- [x] C6 Verify successful agent stdout and summary
  - Verifies: `specs/dag-run-observability/spec.md` / Requirement "Agent execution logs remain queryable" / Scenario "Successful agent keeps stdout and summary"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py tests/core/unit/test_core_architecture_overhaul.py`
  - Expect: 成功 agent 同时保留实时 stdout 行、raw log index 和 execution summary

- [x] C7 Verify failed or silent agent summary
  - Verifies: `specs/dag-run-observability/spec.md` / Requirement "Agent execution logs remain queryable" / Scenario "Failed agent keeps stdout and summary", Scenario "Agent without stdout still has summary"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py`
  - Expect: 失败 agent 和无 stdout agent 都能查询 execution summary，失败时保留已产生 stdout

### Task 4: 日志查询 API 与 BFF

**Goal**: 提供按 `run_id + node_id` 查询 execution logs 的 gRPC/BFF API，并保持 `/api/node-outputs` 只返回业务输出。

**Files**:
- Modify: `proto/edera.proto`
- Modify: `packages/core/src/edera_core/query_service.py`
- Modify: `packages/core/src/edera_core/grpc_client.py`
- Modify: `packages/core/src/edera_core/web/routes.py`
- Test: `packages/core/tests/test_web_routes.py`

**Requirements**:
- gRPC 查询支持按 `run_id` 和 `node_id` 返回 execution logs。
- BFF HTTP route 只通过 `GrpcClient` 调用 server。
- `/api/node-outputs` 不混入 execution logs。

#### Checks

- [x] C8 Verify BFF logs route uses gRPC filters
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "BFF node execution logs API" / Scenario "HTTP logs route uses gRPC", Scenario "Logs query filters by run and node"
  - Command: `uv run pytest packages/core/tests/test_web_routes.py`
  - Expect: HTTP logs route 通过 gRPC client 传递 `run_id` 与 `node_id` 并返回对应日志

- [x] C9 Verify node outputs API remains output-only
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "BFF node execution logs API" / Scenario "Node outputs route remains output-only"
  - Command: `uv run pytest packages/core/tests/test_web_routes.py`
  - Expect: `/api/node-outputs` 响应不包含 execution logs

### Task 5: Web Runtime 与历史展示

**Goal**: 在 Workbench Runtime tab 和 Node History 中展示 execution logs，解决已执行但无业务 output 时的空白体验。

**Files**:
- Modify: `apps/web-console/src/api/types.ts`
- Modify: `apps/web-console/src/api/queries.ts`
- Modify: `apps/web-console/src/features/workbench/components/Inspector.tsx`
- Modify: `apps/web-console/src/features/history/NodeHistoryPage.tsx`
- Test: `apps/web-console/tests/workbench-usability.spec.ts`

**Requirements**:
- Runtime tab 展示 Status、Output entities、Logs 三个区域。
- 已执行但无业务 output 时展示 execution summary log。
- 已执行失败时展示 error 和 execution logs。
- Node History 展开项展示该 run 的 execution logs。

#### Checks

- [x] C10 Verify Runtime tab logs for empty output and failure
  - Verifies: `specs/dag-run-observability/spec.md` / Requirement "Runtime views show execution logs" / Scenario "Runtime tab shows logs for empty output", Scenario "Runtime tab shows failure logs"
  - Command: `npm run verify`
  - Expect: Workbench Runtime tab 在无业务 output 和失败节点场景中展示 execution logs

- [x] C11 Verify Node History logs and unstarted boundary
  - Verifies: `specs/dag-run-observability/spec.md` / Requirement "Runtime views show execution logs" / Scenario "Node history expands logs", Scenario "Unstarted node does not require logs"
  - Command: `npm run verify`
  - Expect: Node History 展开项展示已执行 run 的 logs，未执行节点不要求 logs

### Task 6: CLI 日志命令

**Goal**: 让用户通过 `edera node logs <node> --run-id <run_id>` 查看执行日志，同时保持 `edera node output` 的业务输出语义。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Modify: `packages/core/src/edera_core/grpc_client.py`
- Test: `tests/core/unit/test_core_architecture_overhaul.py`

**Requirements**:
- 新增或扩展 CLI node logs 命令，通过 gRPC 查询 execution logs。
- logs 命令输出 summary 和 raw log reference。
- output 命令继续只返回业务 output。

#### Checks

- [x] C12 Verify node logs command
  - Verifies: `specs/edera-cli/spec.md` / Requirement "Node execution logs command" / Scenario "查看节点执行日志", Scenario "无业务输出仍可看日志"
  - Command: `uv run pytest tests/core/unit/test_core_architecture_overhaul.py`
  - Expect: CLI 可按 `run_id` 查询节点 execution logs，无业务 output 时仍输出 summary

- [x] C13 Verify node output command remains business-only
  - Verifies: `specs/edera-cli/spec.md` / Requirement "Node execution logs command" / Scenario "节点输出命令保持业务语义"
  - Command: `uv run pytest tests/core/unit/test_core_architecture_overhaul.py`
  - Expect: `edera node output` 不返回 execution logs
