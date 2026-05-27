## Context

Edera 当前以 DAG 为执行模型，以 Entity 为统一对象语义。运行期事实目前分散在 `pipeline_runs`、`node_runs`、`NodeOutput.metadata` 和部分简报 metadata 中；source recovery 还会被写成伪造的 source `node_runs`。这导致业务 payload、输入上下文和运行审计混在一起。

当前故障暴露了这个问题：optional 上游失败被 `DagRunner._input_payload()` 转成 `None` 并混入下游 `payload`，`reader` 的 `list[RawItem]` 输入因此收到 `[RawItem..., None]`，触发 `RawItem.model_validate(None)`。这不是页面问题，而是 core runtime 输入契约问题。

## Goals / Non-Goals

**Goals:**

- 保证下游 `payload` 只包含成功上游的业务数据，optional 失败不再以 `None` 占位进入 payload。
- 使用具体 runtime tables 保存运行事实，并通过 Entity API/CLI 投影为 runtime entities。
- 在目标节点调度决策点写入目标节点所有直接入边的 `edge_inputs`。
- 用 `source_recoveries` 表承载 source recovery 最终 summary，删除通过 output metadata 和伪造 source node run 传播的链路。
- 为 function 与 agent 节点提供可见但简短的运行上下文。
- 删除 `fallback: skip`，保留 `fallback: switch_model`。

**Non-Goals:**

- 不把所有 runtime facts 合并进一个通用 `runtime_entities` 表。
- 不记录每条 edge 精确消费了哪些 output ids；需要 payload 时通过 `cycle_id + from_node_id` 查询或 CLI export。
- 不在本变更中实现完整 UI 重做；UI 只消费新的 runtime API/投影。
- 不保留旧的 `fallback: skip` 兼容行为。

## Decisions

### Runtime facts use concrete tables with Entity projection

底层使用具体表：

- `pipeline_runs`
- `node_runs`
- `edge_inputs`
- `source_recoveries`

上层 API/CLI 将这些行投影为 runtime entities，例如 `runtime.edge-input`、`runtime.source-recovery`。这样保留结构化表的索引和约束，同时维持 everything is entity 的统一访问模型。

备选方案是把所有 runtime facts 塞进通用 JSON table。拒绝该方案，因为 `edge_inputs` 和 `source_recoveries` 查询模式固定，通用 JSON 会削弱约束并引入垃圾桶式存储。

### Payload is business data only

`payload` 不再承载 optional failure。多输入聚合只收集成功上游的有效 payload；list 输入在没有有效数据时得到 `[]`。失败、empty、unknown 等入边状态进入 `edge_inputs` 和当前节点输入上下文。

非 list 输入不自动伪造空业务值。若节点需要在空输入下运行，必须通过显式配置声明空输入行为；core 不猜测 `{}`、`""` 或 `0` 这类业务值。

备选方案是在 payload 中保留 `None` 作为占位。拒绝该方案，因为它破坏 `list[T]` 类型契约，并要求每个下游节点重复防御 core 制造的无效业务值。

### Edge input facts are written at target scheduling decision time

当 runner 对目标节点做调度决策时，写入该目标节点所有直接入边的 `edge_inputs`。如果 required 上游失败导致目标节点不运行，也写入所有直接入边，并将目标 `node_runs` 标记为 `status=failed`、`failure_kind=upstream_failed`。

备选方案是在每个上游完成时持续更新所有下游边状态。拒绝该方案，因为它制造中间态、写放大，并且不表达“目标节点实际看到的输入事实”。

### DagRunner emits facts; PipelineController persists

`DagRunner` 负责生成 edge input facts，通过 `edge_recorder` 回调交给 `PipelineController`。`DagRunner` 不直接依赖数据库。`edge_recorder` 写入失败时，DAG run 失败。

该模式复用现有 node run recorder 的边界：runner 拥有调度语义，controller 拥有持久化。

### Source recovery uses explicit runtime API

source fetcher 通过 `ctx.runtime.record_source_recovery(...)` 写入 `source_recoveries` 最终 summary。`source_recoveries` 使用 `unique(cycle_id, node_id, source_name)` upsert，不记录每次 attempt 明细。`_record_source_runs()` 从 output metadata 收集 source recovery 的模式删除，`node_runs` 不再写 source name 伪记录。

备选方案是继续写 `ctx.input.metadata["source_recovery"]` 并向下游 output metadata 传播。拒绝该方案，因为它把 run-level facts 混入 input/output metadata，越往下游越污染。

### Metadata no longer propagates automatically to output metadata

`NodeInput.metadata` 表示当前节点输入上下文。`NodeOutput.metadata` 只表示节点自身输出事实，例如 `session_id`、loop/sub-DAG 结果。输入侧 `upstream_statuses`、`source_recovery`、`failures` 不自动复制到 output metadata。

### Agent context is short by default

agent 节点默认获得简短 runtime context 和 `runtime-context.json`。该文件是运行索引，不是 payload 搬运通道。agent 需要业务 payload 时，通过 CLI export 到自己的运行目录文件。

### Remove fallback skip

`fallback: skip` 删除并在配置校验层拒绝。`fallback: switch_model` 保留，因为它是重试策略，不伪装失败语义。

## Risks / Trade-offs

- [Risk] runtime tables 引入迁移和 repository 改动。→ Mitigation: 只增加必要字段和表，保持 `node_outputs` 业务输出表职责不变。
- [Risk] 删除 `fallback: skip` 会让已有配置校验失败。→ Mitigation: 当前项目无历史负担，失败配置应显式修正为 edge optional 或 switch_model。
- [Risk] 不记录 output refs 会降低精确血缘。→ Mitigation: 第一版通过 `cycle_id + from_node_id` 查询上游输出，避免过早复杂化。
- [Risk] agent runtime context 可能泄露过长错误。→ Mitigation: prompt 和 `runtime-context.json` 只写摘要，完整 payload 需显式 CLI export。
