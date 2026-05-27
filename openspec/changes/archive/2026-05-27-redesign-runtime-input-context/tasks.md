## 1. Actions

- [x] A1 增加 runtime storage 模型和 repository API：`edge_inputs`、`source_recoveries`、`node_runs.failure_kind`，并保持 runtime facts 不写入 `node_outputs`
- [x] A2 重写 `DagRunner` 多输入聚合和 optional 语义：移除 `None` 占位，list 输入无有效数据时传 `[]`
- [x] A3 为 `DagRunner` 增加 edge input fact 生成和 `edge_recorder` 回调，在目标节点调度决策点写入所有直接入边
- [x] A4 删除 `fallback: skip` schema 与执行逻辑，保留 `fallback: switch_model`
- [x] A5 增加 `RuntimeContextProtocol` 和 `ctx.runtime.record_source_recovery(...)`，迁移 source fetcher 写入 source recovery 的方式
- [x] A6 删除旧 source recovery 收集链路：移除 `_record_source_runs()` / `_source_recovery()` 从 `NodeOutput.metadata` 收集 source recovery 的模式，并停止伪造 source `node_runs`
- [x] A7 改造 source health/logs API：从 `source_recoveries` 与真实 source fetcher `node_runs` 读取，不再依赖 Briefing metadata 或伪造 source node run
- [x] A8 改造 retry/resume 输入重建：optional 历史缺失允许继续并写 `unknown/failed` edge input，required 历史缺失标记 `upstream_failed`
- [x] A9 为 agent 节点生成简短 runtime context 和 `runtime-context.json`，并提供 `edera node output export --cycle <cycle_id> --node <node_id> --out <path>` CLI 路径
- [x] A10 停止自动复制 `NodeInput.metadata` 到 `NodeOutput.metadata`，将 output metadata 限定为节点自身输出元信息
- [x] A11 补齐单元、集成和回归测试，覆盖 `RawItem(None)`、edge_inputs、source_recoveries、retry、agent context 和默认 `error_summary`

## 2. Checks

- [x] C1 Verify runtime tables and repository contracts
  - Covers: A1
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Runtime facts storage model" / Scenario "Project runtime facts as entities"
  - Command: `uv run pytest tests/core/unit tests/core/integration -k "runtime or edge_input or source_recovery"`
  - Expect: runtime facts 使用具体表存储，并能投影为 runtime entities

- [x] C2 Verify business outputs stay separate from runtime facts
  - Covers: A1
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Runtime facts storage model" / Scenario "Keep business outputs separate"
  - Command: `uv run pytest tests/core/integration -k "node_outputs or runtime"`
  - Expect: `edge_inputs` 和 `source_recoveries` 不写入 `node_outputs`

- [x] C3 Verify optional failures are excluded from payload
  - Covers: A2, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Payload aggregation excludes runtime failures" / Scenario "Optional failed input excluded from list payload"
  - Command: `uv run pytest tests/core/integration/test_dag_runner.py -k "optional"`
  - Expect: 下游 list payload 只包含成功上游数据，不包含 `None`

- [x] C4 Verify empty list input continues execution
  - Covers: A2, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Payload aggregation excludes runtime failures" / Scenario "No successful list inputs"
  - Command: `uv run pytest tests/core/integration/test_dag_runner.py -k "empty or optional"`
  - Expect: 所有 optional 上游失败时，list 输入节点收到 `[]` 并继续运行

- [x] C5 Verify edge input facts are recorded for scheduling decisions
  - Covers: A3, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Edge input facts" / Scenario "Failed edge input"
  - Command: `uv run pytest tests/core/integration -k "edge_input"`
  - Expect: optional 上游失败写入 `status=failed`、`has_payload=false` 和非空 `error_summary`

- [x] C6 Verify required upstream failure marks downstream as upstream_failed
  - Covers: A3, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Node failure kind" / Scenario "Upstream failure kind"
  - Command: `uv run pytest tests/core/integration/test_dag_runner.py -k "required or upstream_failed"`
  - Expect: required 上游失败时目标节点不执行，`node_runs.failure_kind=upstream_failed`

- [x] C7 Verify edge inputs include all direct inbound edges when blocked
  - Covers: A3, A11
  - Verifies: `specs/dag-event-driven-executor/spec.md` / Requirement "Fan-in barrier 增加 edge optional 判定" / Scenario "所有 required 边上游失败阻塞下游"
  - Command: `uv run pytest tests/core/integration -k "edge_input and blocked"`
  - Expect: 目标节点因 required 上游失败不运行时，其所有直接入边均写入 `edge_inputs`

- [x] C8 Verify fallback skip is rejected while switch_model remains
  - Covers: A4, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Node failure kind" / Scenario "Execution failure kind"
  - Command: `uv run pytest tests/core/unit tests/core/integration -k "fallback"`
  - Expect: `fallback: skip` 配置校验失败，`fallback: switch_model` 仍按重试语义工作

- [x] C9 Verify source recovery runtime API persists final summary
  - Covers: A5, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Source recovery runtime facts" / Scenario "Record final source recovery summary"
  - Command: `uv run pytest tests/core/unit tests/core/integration -k "source_recovery"`
  - Expect: source fetcher 通过 `ctx.runtime.record_source_recovery(...)` upsert `source_recoveries`

- [x] C10 Verify source recovery unique upsert
  - Covers: A5, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Source recovery runtime facts" / Scenario "Source recovery unique key"
  - Command: `uv run pytest tests/core/unit tests/core/integration -k "source_recovery"`
  - Expect: 同一 `cycle_id + node_id + source_name` 只保留最终 summary，不追加 attempt 明细

- [x] C11 Verify legacy source recovery collection is removed
  - Covers: A6, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Source recovery runtime facts" / Scenario "Legacy source recovery collection removed"
  - Command: `uv run pytest tests/core/unit tests/core/integration -k "source_recovery"`
  - Expect: source recovery 不再通过 `NodeOutput.metadata.source_recovery`、`_record_source_runs()` 或 `_source_recovery()` 传播

- [x] C12 Verify source health reads source_recoveries and real node runs
  - Covers: A7, A11
  - Verifies: `specs/source-health-monitoring/spec.md` / Requirement "Latest source failure reason" / Scenario "Use source recovery failure reason"
  - Command: `uv run pytest tests/core/integration -k "source_health"`
  - Expect: source health 优先展示 `source_recoveries.latest_failure_reason`

- [x] C13 Verify no fake source node_runs are created
  - Covers: A6, A7, A11
  - Verifies: `specs/source-health-monitoring/spec.md` / Requirement "Source execution logs" / Scenario "List source execution logs"
  - Command: `uv run pytest tests/core/integration -k "source_logs or source_health"`
  - Expect: `node_runs` 只包含真实 node instance，source logs 从真实 node runs 与 `source_recoveries` 组合返回

- [x] C14 Verify retry allows missing optional historical upstream
  - Covers: A8, A11
  - Verifies: `specs/dag-run-control/spec.md` / Requirement "节点重试" / Scenario "Optional historical upstream missing"
  - Command: `uv run pytest tests/core/integration/test_per_dag.py -k "retry"`
  - Expect: optional 历史上游无 output 时 retry 继续运行，并写入 `failed` 或 `unknown` edge input

- [x] C15 Verify retry blocks missing required historical upstream
  - Covers: A8, A11
  - Verifies: `specs/dag-run-control/spec.md` / Requirement "节点重试" / Scenario "Required historical upstream missing"
  - Command: `uv run pytest tests/core/integration/test_per_dag.py -k "retry"`
  - Expect: required 历史上游无 output 时目标节点失败，`failure_kind=upstream_failed`

- [x] C16 Verify agent runtime context and explicit payload export
  - Covers: A9, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Agent runtime context" / Scenario "Agent receives short context"
  - Command: `uv run pytest tests/core/unit tests/core/integration -k "agent and context"`
  - Expect: agent 运行目录包含 `runtime-context.json`，prompt 仅注入简短上下文

- [x] C17 Verify CLI exports payload to file on demand
  - Covers: A9, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Agent runtime context" / Scenario "Agent exports payload explicitly"
  - Command: `uv run pytest tests/core/unit -k "rig_cli or node_output"`
  - Expect: CLI 支持 `edera node output export --cycle <cycle_id> --node <node_id> --out <path>`，默认不向 prompt 注入完整 payload

- [x] C18 Verify input metadata is not copied to output metadata
  - Covers: A10, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Output metadata boundary" / Scenario "Input context not copied to output"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py -k "metadata"`
  - Expect: `upstream_statuses`、`source_recovery`、`failures` 不再自动进入 `NodeOutput.metadata`

- [x] C19 Verify non-list empty input is not fabricated
  - Covers: A2, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Payload aggregation excludes runtime failures" / Scenario "No automatic empty value for non-list inputs"
  - Command: `uv run pytest tests/core/integration/test_dag_runner.py -k "empty or optional"`
  - Expect: 非 list 输入在 optional 上游均无有效 payload 时不会被自动伪造 `{}`、`""` 或 `0`

- [x] C20 Verify failed edge input default error summary
  - Covers: A3, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Edge input facts" / Scenario "Failed edge input with empty error"
  - Command: `uv run pytest tests/core/integration -k "edge_input"`
  - Expect: 上游失败且 error 为空时，`edge_inputs.error_summary` 为 `node failed`

- [x] C21 Verify edge inputs store node ids only
  - Covers: A1, A3, A11
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Edge input facts" / Scenario "Edge input stores node ids only"
  - Command: `uv run pytest tests/core/unit tests/core/integration -k "edge_input"`
  - Expect: `edge_inputs` 持久化字段不包含 alias、node type 或 output refs
