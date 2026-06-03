## Context

后端干预能力已全栈就绪：
- gRPC `NodeService.Stop(NodeRef)` → soft stop（`executor.stop_agent` 置位、pi 当前轮次完成后退出、session 保留）。
- gRPC `NodeService.Resume(NodeResumeRequest{id, run_id, prompt})` → `payload={resume_session: "sandbox:<id>:<run_id>", prompt}`，`resume_node` 以 `--continue` 续跑，输出替换 + 下游 cascade retry（见 `llm-node-intervention` spec）。
- BFF HTTP：`POST /api/node/{id}/stop`、`POST /api/node/{id}/resume`（body: `run_id`、`prompt`）、`GET /api/node/{id}/status`、SSE `GET /api/events/node/{id}`。
- 前端 `grpc_client` 侧 `node_stop/node_resume/node_status` 已存在；`queries.ts` 暂无对应 React Query hooks。

工作台节点 `CustomNode` 已通过 `getRuntimeState(status)` 展示 running 等运行态，弹窗可挂此处。现有 `NewSourceDialog` 提供弹窗组件范式。

## Goals / Non-Goals

**Goals:**
- 在工作台运行视图为 agent 节点提供交互弹窗。
- 区分「运行中中断+注入」与「已结束直接发送」两条干预路径。
- 复用既有后端语义（输出替换、cascade retry），前端不引入新后端 RPC。

**Non-Goals:**
- 不改后端 stop/resume 语义与协议。
- 不做通用 wait 节点交互（属 `dag-node-wait-input` change）。
- 不做节点类型管理页（`NodesPage`）改动——干预入口属运行视图，不属配置管理页。

## Decisions

**D1：弹窗挂载在工作台运行视图的 agent 节点，而非 NodesPage。**
理由：用户需「看到 node 正在运行」才干预，`NodesPage` 是节点类型/Skills 配置页、无运行实例上下文。运行态由 `CustomNode` 的 `getRuntimeState` 已经呈现，触发点自然落此。

**D2：运行中干预 = stop 后 resume 的前端编排，不新增原子 RPC。**
弹窗在节点 `running` 时提交：先 `POST /stop` 等 soft stop 生效（节点转入非运行态/可续跑），再 `POST /resume{run_id, prompt}`。已结束节点直接 `POST /resume{run_id, prompt}`。两路径共用同一弹窗，按节点当前 `runtimeState` 选择编排。备选（新增后端 `Intervene` 原子 RPC）被否：现有两 RPC 足以编排，新增徒增协议面与维护成本。

**D3：节点运行态判定来源 = SSE + status 查询。**
弹窗打开时以 `GET /api/node/{id}/status` 取当前态，运行期间订阅 `GET /api/events/node/{id}` SSE 实时更新，决定走「中断+注入」还是「直接发送」。

**D4：干预后果交给后端既有语义。**
输出替换（更新 `NodeOutput`）与下游 cascade retry 由 `resume_node` 既有实现负责，前端仅在 resume 返回新 `run_id` 后刷新相关查询缓存。

## Risks / Trade-offs

- **stop→resume 非原子，中间态可见**：stop 后、resume 前节点短暂处于停止态。→ 弹窗在编排期间显示 pending 态、禁用重复提交；resume 失败可重试。
- **soft stop 生效有延迟（当前轮次完成才退出）**：用户点「中断」后非立即停止。→ 弹窗文案明确说明「当前轮次完成后注入」，避免误解为强制打断。
- **并发干预同一节点**：多个客户端同时干预。→ 依赖后端单 `run_id` resume 串行语义；前端提交期间禁用按钮。

## Migration Plan

纯前端增量，无后端/协议改动，无数据迁移。回滚：移除弹窗组件与 hooks 即可，后端能力不受影响。

## Open Questions

- 弹窗是否需要展示节点当前输出/会话历史预览以辅助干预决策？倾向首版仅展示状态 + prompt 输入框，历史预览后续迭代。
