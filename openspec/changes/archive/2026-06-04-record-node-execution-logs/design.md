## Context

当前执行路径已经分别记录 `NodeRun` 状态、`NodeOutputEntity` 业务输出、agent stdout SSE 和 raw log file index，但缺少统一的“已执行节点日志”契约。结果是节点实际运行过却没有业务 payload 或失败时，Runtime/History 只能展示空 output 列表，用户无法判断执行过程。

本设计沿用现有 SQLite、SQLModel、gRPC JsonResponse、BFF route、event_bus/SSE 和 Web Console 页面，不引入外部依赖。

## Goals / Non-Goals

**Goals:**

- 每个实际开始执行的 node run 都有可查询 execution log。
- execution log 至少包含系统生成的执行摘要；agent stdout/raw log 也通过同一查询面可见。
- `node_outputs` 继续只保存真实业务输出，不保存失败摘要或空 payload 占位。
- Runtime tab、Node History 和 CLI 都能按 `run_id + node_id` 查看执行日志。

**Non-Goals:**

- 不要求未启动节点生成日志，例如 required 上游失败导致的 `upstream_failed`。
- 不捕获普通 Python handler 的 stdout/stderr，除非现有执行路径已经提供输出流。
- 不把 execution logs 作为 retry/resume 的输入重建来源。
- 不新增前端页面；只扩展现有 Runtime/History 展示。

## Decisions

1. 使用 execution logs 作为通用可观测面，而不是扩大 `NodeOutputEntity` 语义。

   - 选择：成功且有业务 payload 时继续写 `node_outputs`；失败、空 payload、系统摘要写 execution logs。
   - 理由：`node_outputs` 是下游数据流和 retry/resume 的业务来源，混入失败摘要会污染执行语义。
   - 替代方案：所有失败都写 `node_outputs`。拒绝，原因是会把未产出业务数据的失败伪装成业务 output。

2. 使用 `log_index` 索引 summary log 和 raw process log。

   - 选择：系统摘要写成小型结构化 log 文件并由 `log_index` 索引；agent stdout 继续写 raw log 并索引。
   - 理由：已有 `LogIndex` 模型和 raw log 文件约束，适合承载可查询日志入口；大文本不进入 runtime facts 表。
   - 替代方案：把摘要直接塞进 `NodeRun.metadata`。拒绝，原因是会让 `NodeRun` 同时承担状态与日志存储，边界变脏。

3. 由执行收口层保证“已执行才有日志”。

   - 选择：NodeRun 进入 `running` 后的实际执行路径必须在结束时写 summary log，覆盖 function、wait、dag 和 agent。
   - 理由：只有执行收口层知道最终 `ok`、`error`、`payload_empty`、`session_id`、raw log ref 等信息。
   - 替代方案：前端在无 output 时显示 NodeRun.error。拒绝，原因是成功空 payload 和失败无 stdout 仍然缺少稳定日志记录。

4. API 读取保持查询型，不改变 output API 语义。

   - 选择：新增或扩展节点日志查询接口，Runtime/History 同时请求 outputs 和 logs。
   - 理由：保持 `/api/node-outputs` 兼容，避免旧调用者把日志当 output。
   - 替代方案：在 `/api/node-outputs` 中混合返回日志。拒绝，原因是 API 名称和返回语义不一致。

## Risks / Trade-offs

- 日志与业务输出混淆 → 通过独立 execution log 查询面和 specs 明确禁止把失败摘要写入 `node_outputs`。
- 日志量增长 → raw stdout/stderr 继续落文件，DB 只保存索引；summary log 保持小而结构化。
- UI 信息变多 → Runtime/History 使用 `Status`、`Outputs`、`Logs` 分区；无业务 output 时仍可直接查看 logs。
- 空 payload 误判为未执行 → summary log 明确记录 `ok=true` 和 `payload_empty=true`。
