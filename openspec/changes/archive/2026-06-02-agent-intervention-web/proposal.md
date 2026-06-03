<!--
propose-decision:
  designSummary: found (from /opsx:explore)
  routing: skip-explore (Design Summary present)
  scope: change 2 of 2 (agent intervention web exposure); change 1 = dag-node-wait-input
  finding: 后端 gRPC NodeService.Stop/Resume/Status 与 BFF HTTP /api/node/{id}/* 已存在；本期补前端弹窗与运行时中断注入编排
-->

## Why

`llm-node-intervention` 的 stop + resume 干预能力在后端已全栈打通（gRPC `NodeService.Stop/Resume/Status` + BFF HTTP `/api/node/{id}/stop|resume|status` + SSE `/api/events/node/{id}`），但 Web Console 没有任何交互入口，干预目前只能走 `edera` CLI。需要在能「看到 node 正在运行」的工作台视图提供 agent 交互弹窗，覆盖两种语义：运行中节点「中断现有内容后注入用户输入」，以及已结束节点「直接发送干预 prompt 重跑」。

## What Changes

- Web Console 新增 **agent 交互弹窗**，从 DAG 工作台运行视图中正在运行/已结束的 agent 节点触发。
- **运行中干预**：弹窗发送后先 `stop`（soft stop，当前轮次完成后退出、session 保留）再 `resume(prompt)`，实现「中断现有内容后加入用户输入」。
- **已结束干预**：直接 `resume(prompt)`，复用 `--continue` 从原 sandbox 续跑。
- 前端新增 `useNodeStop` / `useNodeResume` / `useNodeStatus` mutation/query hooks，对接现有 BFF HTTP 路由。
- 弹窗展示节点实时状态（复用 `getRuntimeState` 与 SSE），干预后输出替换与下游 cascade retry 由现有后端语义处理。

## Capabilities

### New Capabilities
- `agent-intervention-web`: Web Console agent 交互弹窗、运行中「中断+注入」与已结束「直接发送」两种干预编排、前端干预 hooks 与实时状态展示。

### Modified Capabilities
（无 spec 级行为变更；后端 `llm-node-intervention` 行为复用不改。）

## Impact

- `apps/web-console/src/api/queries.ts`：新增 `useNodeStop`/`useNodeResume`/`useNodeStatus` hooks。
- `apps/web-console/src/features/workbench/`：新增 agent 交互弹窗组件，挂载到运行视图中 agent 节点的触发入口（参照 `NewSourceDialog` 模式）。
- `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`：agent 节点暴露干预触发点。
- 后端：无改动（gRPC/HTTP/SSE 已就绪）；若 stop→resume 需原子编排保证，前端按序调用现有两个端点。
