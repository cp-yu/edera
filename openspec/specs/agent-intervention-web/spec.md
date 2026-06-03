---
capabilities:
  - cap.web.agent-intervention-web
---
# agent-intervention-web Specification

## Purpose
定义 Agent 交互弹窗入口、运行中节点中断后注入、已结束节点直接发送、前端干预 hooks。
## Requirements
### Requirement: Agent 交互弹窗入口
Web Console SHALL 在 DAG 工作台运行视图为 agent 节点提供交互弹窗触发入口。弹窗 MUST 仅对 agent 类型节点可用，并 MUST 展示该节点当前运行状态。

#### Scenario: agent 节点暴露干预入口
- **WHEN** 工作台运行视图中存在 agent 类型节点
- **THEN** 该节点 SHALL 提供打开交互弹窗的触发点

#### Scenario: 弹窗展示节点状态
- **WHEN** 用户打开某 agent 节点的交互弹窗
- **THEN** 弹窗 SHALL 通过 `GET /api/node/{id}/status` 展示该节点当前运行状态

### Requirement: 运行中节点中断后注入
当目标 agent 节点处于运行态，弹窗提交干预 prompt 时系统 SHALL 先调用 `POST /api/node/{id}/stop` 执行 soft stop，待停止生效后再调用 `POST /api/node/{id}/resume`（携带 `run_id` 与 `prompt`），实现「中断现有内容后加入用户输入」。

#### Scenario: 运行中干预走 stop 再 resume
- **WHEN** agent 节点处于 `running`，用户在弹窗输入 prompt 并提交
- **THEN** 系统 SHALL 先 `POST /api/node/{id}/stop`，stop 生效后再 `POST /api/node/{id}/resume` 携带 `run_id` 与 `prompt`

#### Scenario: 编排期间禁止重复提交
- **WHEN** stop→resume 编排进行中
- **THEN** 弹窗 SHALL 处于 pending 态并禁用重复提交

### Requirement: 已结束节点直接发送
当目标 agent 节点已结束（非运行态），弹窗提交干预 prompt 时系统 SHALL 直接调用 `POST /api/node/{id}/resume`（携带 `run_id` 与 `prompt`），复用 `--continue` 从原 sandbox 续跑，不调用 stop。

#### Scenario: 已结束节点直接 resume
- **WHEN** agent 节点已结束，用户在弹窗输入 prompt 并提交
- **THEN** 系统 SHALL 直接 `POST /api/node/{id}/resume` 携带 `run_id` 与 `prompt`，不调用 stop

### Requirement: 前端干预 hooks
Web Console SHALL 在 `queries.ts` 提供 `useNodeStop`、`useNodeResume`、`useNodeStatus` hooks，分别对接现有 BFF HTTP 路由。`useNodeResume` 成功返回新 `run_id` 后 MUST 失效相关节点输出查询缓存以刷新视图。

#### Scenario: resume 成功后刷新缓存
- **WHEN** `useNodeResume` 调用成功并返回新 `run_id`
- **THEN** 系统 SHALL 失效该节点相关的输出查询缓存

#### Scenario: hooks 对接既有路由
- **WHEN** 调用 `useNodeStop`/`useNodeResume`/`useNodeStatus`
- **THEN** 它们 SHALL 分别请求 `/api/node/{id}/stop`、`/api/node/{id}/resume`、`/api/node/{id}/status`，不新增后端端点
