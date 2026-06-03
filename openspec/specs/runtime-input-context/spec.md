---
capabilities:
  - cap.core.runtime-input-context
---
# runtime-input-context Specification

## Purpose
此规约记录变更 redesign-runtime-input-context 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Runtime facts storage model
系统 SHALL 使用具体 runtime tables 存储已提交运行事实，并通过 Entity API/CLI 将这些运行事实投影为 runtime entities。运行中调度状态 SHALL 以内存 runtime snapshot 和 runner state 为准。系统 MUST NOT 将 `edge_inputs` 或 `source_recoveries` 存入 `node_outputs`。

#### Scenario: Project runtime facts as entities
- **WHEN** 用户通过 API 或 CLI 查询某个 run 的 runtime facts
- **THEN** 系统 SHALL 将底层 `dag_runs`、`node_runs`、`edge_inputs` 和 `source_recoveries` 行投影为 runtime entities

#### Scenario: Keep business outputs separate
- **WHEN** 节点产出业务 payload
- **THEN** 系统 SHALL 继续将业务输出写入 `node_outputs`，并 MUST NOT 将 runtime facts 混入业务输出表

#### Scenario: Active runtime state stays in memory
- **WHEN** DAG runner 正在调度节点、聚合 payload 或判断 edge 状态
- **THEN** 系统 SHALL 使用内存中的 runtime state 和 committed snapshot 作决策
- **AND** runtime tables SHALL 只作为提交事实和查询投影来源

### Requirement: Edge input facts
系统 SHALL 定义 `edge_inputs` runtime table，字段 MUST 包含 `run_id`、`from_node_id`、`to_node_id`、`edge_optional`、`status`、`has_payload` 和 `error_summary`。`edge_inputs.status` MUST 仅允许 `available`、`empty`、`failed`、`unknown`。`edge_inputs` MUST NOT 存储 alias、node type 或 output refs。

#### Scenario: Edge input unique key
- **WHEN** 系统写入某个 run 中同一条 `from_node_id -> to_node_id` 的 edge input fact
- **THEN** 系统 MUST 使用 `run_id + from_node_id + to_node_id` 作为唯一约束，并在 resume 同一 run 时 upsert

#### Scenario: Available edge input
- **WHEN** 上游节点成功且存在有效 payload
- **THEN** 对应 `edge_inputs` 记录 SHALL 使用 `status=available` 且 `has_payload=true`

#### Scenario: Empty edge input
- **WHEN** 上游节点成功但 payload 为空或 `None`
- **THEN** 对应 `edge_inputs` 记录 SHALL 使用 `status=empty` 且 `has_payload=false`

#### Scenario: Failed edge input
- **WHEN** 上游节点失败
- **THEN** 对应 `edge_inputs` 记录 SHALL 使用 `status=failed`、`has_payload=false`，并填充非空 `error_summary`

#### Scenario: Failed edge input with empty error
- **WHEN** 上游节点失败且错误信息为空字符串或 `None`
- **THEN** 对应 `edge_inputs.error_summary` MUST 使用默认值 `node failed`

#### Scenario: Edge input stores node ids only
- **WHEN** 系统写入 `edge_inputs`
- **THEN** 记录 MUST 只存储 `from_node_id` 和 `to_node_id`，alias 与 node type SHALL 由 runtime entity projection 层补齐

#### Scenario: Unknown historical edge input
- **WHEN** retry 或 resume 无法从历史 runtime tables 找到 optional 上游状态
- **THEN** 对应 `edge_inputs` 记录 SHALL 使用 `status=unknown` 且允许目标节点继续执行

### Requirement: Payload aggregation excludes runtime failures
系统 SHALL 在构造下游 `payload` 时只聚合成功上游的业务数据。Optional 上游失败 MUST NOT 以 `None`、`null` 或其他占位符进入 `payload`。

#### Scenario: Optional failed input excluded from list payload
- **WHEN** 节点 C 有 optional 上游 A 失败，且上游 B 成功输出 `[raw1, raw2]`
- **THEN** 节点 C 接收的 `payload` MUST 为 `[raw1, raw2]`

#### Scenario: No successful list inputs
- **WHEN** 节点 C 的所有直接上游均为 optional 且均失败或无 payload，且 C 的 input type 为 list
- **THEN** 节点 C SHALL 继续执行，并接收 `payload=[]`

#### Scenario: No automatic empty value for non-list inputs
- **WHEN** 节点 C 的所有直接上游均为 optional 且均失败或无 payload，且 C 的 input type 不是 list
- **THEN** 系统 MUST NOT 自动伪造 `{}`、`""`、`0` 或其他业务值；节点若需在空输入下运行 MUST 通过显式配置声明空输入行为

### Requirement: Node failure kind
系统 SHALL 在 `node_runs` 记录中区分节点自身执行失败和 required 上游失败导致的未执行失败。`node_runs.failure_kind` MUST 支持 `execution_failed`、`upstream_failed` 和 `null`。

#### Scenario: Execution failure kind
- **WHEN** 节点已经启动并执行失败
- **THEN** 系统 SHALL 记录 `status=failed` 且 `failure_kind=execution_failed`

#### Scenario: Upstream failure kind
- **WHEN** required 上游失败导致目标节点不启动
- **THEN** 系统 SHALL 记录目标节点 `status=failed`、`failure_kind=upstream_failed`，并在 error 中说明阻断上游

### Requirement: Source recovery runtime facts
系统 SHALL 定义 `source_recoveries` runtime table，用于保存每个 source 在某个 run/node 下的最终恢复 summary。表字段 MUST 包含 `run_id`、`node_id`、`source_name`、`recovery_status`、`attempt_count`、`recoverable_reason`、`latest_failure_reason`、`escalated`、`escalation_reason` 和 `created_at`。

#### Scenario: Record final source recovery summary
- **WHEN** source fetcher 完成某个 source 的获取和恢复流程
- **THEN** handler SHALL 通过 `ctx.runtime.record_source_recovery(...)` 写入或更新 `source_recoveries`

#### Scenario: Source recovery unique key
- **WHEN** 同一 `run_id + node_id + source_name` 多次写入 source recovery summary
- **THEN** 系统 MUST upsert 最终 summary，而不是追加 attempt 明细

#### Scenario: Legacy source recovery collection removed
- **WHEN** source fetcher 写入 source recovery
- **THEN** 系统 MUST NOT 通过 `NodeOutput.metadata.source_recovery`、`DagController._record_source_runs()` 或 `_source_recovery()` 从 output metadata 收集 source recovery

### Requirement: Agent runtime context
系统 SHALL 为 agent 节点默认提供简短 runtime context，并在 agent 运行目录写入 `runtime-context.json`。该 context SHALL 包含 run、dag、node 和直接上游 edge input 摘要，但 MUST NOT 自动复制上游 payload。

#### Scenario: Agent receives short context
- **WHEN** agent 节点启动
- **THEN** 系统 SHALL 在 prompt 中注入简短 runtime context，并在运行目录提供 `runtime-context.json`

#### Scenario: Agent exports payload explicitly
- **WHEN** agent 需要查看上游 payload
- **THEN** agent SHALL 使用 `edera node output export --run-id <run_id> --node <node_id> --out <path>` 显式 export payload 到运行目录文件，而不是依赖 prompt 自动携带完整 payload

### Requirement: Output metadata boundary
系统 SHALL 将 `NodeInput.metadata` 视为当前节点输入上下文，将 `NodeOutput.metadata` 视为节点自身输出元信息。系统 MUST NOT 自动将输入侧 metadata 复制到 output metadata。

#### Scenario: Input context not copied to output
- **WHEN** 节点输入 metadata 包含 `upstream_statuses` 或 source recovery context
- **THEN** 系统 MUST NOT 自动将这些字段写入该节点的 `NodeOutput.metadata`

