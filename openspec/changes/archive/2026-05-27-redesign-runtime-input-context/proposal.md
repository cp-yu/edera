## Why

当前 DAG runtime 将 optional 上游失败以 `None` 占位塞进下游 `payload`，破坏了 `list[RawItem]` 等强类型输入契约，并导致 `RawItem.model_validate(None)` 这类核心运行错误。与此同时，source recovery 通过 `NodeOutput.metadata` 和伪造的 `node_runs` source 记录传播，运行事实、业务输出和输入上下文边界混乱。

## What Changes

- **BREAKING**: 删除 `fallback: skip`，节点失败不再被伪装成成功；保留 `fallback: switch_model`。
- **BREAKING**: optional 上游失败不再以 `None` 进入下游 `payload`；`payload` 只包含成功上游业务数据，list 输入无数据时传 `[]`。
- 新增 runtime tables 承载运行事实：`edge_inputs`、`source_recoveries`，并扩展 `node_runs.failure_kind`。
- `edge_inputs` 在目标节点调度决策点写入目标节点所有直接入边状态，包括 required 上游失败导致目标节点不运行的场景。
- `source_recoveries` 通过显式 runtime API 写入最终 source recovery summary，不再经由 `ctx.input.metadata`、`NodeOutput.metadata` 或伪造 source `node_runs` 传播。
- 停止把输入侧 metadata 自动复制到 output metadata；`NodeOutput.metadata` 只描述节点自身输出事实。
- agent 节点默认获得简短 runtime context，并可通过 CLI 将需要的 payload 显式 export 到运行目录文件。

## Capabilities

### New Capabilities
- `runtime-input-context`: 定义 runtime tables、edge input facts、source recovery facts、干净 payload 聚合、agent runtime context 和 CLI export 语义。

### Modified Capabilities
- `edge-optional`: optional 失败不再向 payload 注入 `null`，改为 runtime facts/context 记录失败。
- `dag-event-driven-executor`: dispatcher 在调度决策点写入直接入边 facts，并用 `failure_kind=upstream_failed` 标记 required 上游失败导致的节点失败。
- `dag-run-control`: retry/resume 使用历史 runtime facts 和 node outputs 恢复输入上下文，optional 历史缺失允许继续，required 历史缺失阻断。
- `handler-context-protocol`: HandlerContext 增加显式 runtime API，function 节点通过输入上下文或 runtime API 获取运行事实。
- `source-health-monitoring`: source health 和 logs 改为读取 `source_recoveries` 与真实 node runs，不再依赖 Briefing metadata 或伪造 source node run。

## Impact

- Core runtime: `DagRunner` 输入聚合、ready/block 判定、edge recorder 回调、agent prompt/context 文件生成。
- Pipeline/storage: runtime tables、repository 查询、retry prefill、source recovery persistence、node run failure kind。
- Extension protocol: `HandlerContext` 增加 runtime API，source fetchers 改用 `ctx.runtime.record_source_recovery(...)`。
- CLI/API/UI: runtime entity projection、node output export、source health/logs 数据源调整。
- Tests/specs: optional edge、retry、source recovery、agent context、RawItem 输入防污染覆盖。
