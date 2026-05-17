## Context

`useRuntimeStatus()` 在 `queries.ts:20` 无 `refetchInterval`，仅组件挂载时请求一次 `GET /api/graph/runtime-status`。而 `useDagStatus` 已有条件轮询模式（`refetchInterval: polling ? 2000 : false`）。

## Goals / Non-Goals

**Goals:**
- DAG 运行期间，画布节点状态每 2 秒刷新一次
- 运行结束后停止轮询，避免无意义请求

**Non-Goals:**
- 不引入 WebSocket 或 SSE 实时推送
- 不修改后端 `GET /api/graph/runtime-status` 的响应结构

## Decisions

### D1: 轮询间隔

**选择**：2000ms，与 `useDagStatus` 保持一致

**理由**：节点状态变化频率与 DAG 运行状态一致，统一间隔避免视觉不同步。

### D2: 轮询启停机制

**选择**：`useRuntimeStatus` 接受 `polling: boolean` 参数，由 `WorkbenchPage` 传入 `isRunning`

**理由**：复用已有的 `useDagStatus` 模式，改动最小。

## Risks / Trade-offs

- [Risk] 2s 轮询增加后端负载 → 该接口仅查询最近一次 pipeline run 的 node_runs，查询量小，可接受
- [Risk] 运行结束瞬间可能多一次无效请求 → `isRunning` 由 `dagStatus.data?.current_cycle_id` 驱动，dagStatus 本身也在轮询，延迟可忽略
