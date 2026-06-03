### Task 1: 前端干预 hooks

**Goal**: 在 queries.ts 新增 `useNodeStop`/`useNodeResume`/`useNodeStatus`，对接现有 BFF HTTP 路由。

**Files**:
- Modify: `apps/web-console/src/api/queries.ts`

**Requirements**:
- `useNodeStop(nodeId)` → `POST /api/node/{id}/stop`
- `useNodeResume(nodeId)` → `POST /api/node/{id}/resume`，body 含 `run_id`、`prompt`
- `useNodeStatus(nodeId)` → `GET /api/node/{id}/status`
- `useNodeResume` 成功后失效该节点输出查询缓存
- 不新增后端端点

#### Checks

- [x] C1 Verify hooks 对接既有路由
  - Verifies: `specs/agent-intervention-web/spec.md` / Requirement "前端干预 hooks" / Scenario "hooks 对接既有路由"
  - Command: `cd apps/web-console && npx tsc -b`
  - Expect: 类型检查通过，三 hooks 请求路径分别为 `/api/node/{id}/stop|resume|status`

- [x] C2 Verify resume 成功后刷新缓存
  - Verifies: `specs/agent-intervention-web/spec.md` / Requirement "前端干预 hooks" / Scenario "resume 成功后刷新缓存"
  - Evidence: `apps/web-console/src/api/queries.ts` 中 `useNodeResume` 的 `onSuccess` 调用 `invalidateQueries` 失效节点输出查询
  - Expect: resume mutation 成功回调含缓存失效逻辑

### Task 2: Agent 交互弹窗组件

**Goal**: 新增 agent 交互弹窗，展示节点状态并按运行态选择干预编排。

**Files**:
- Create: `apps/web-console/src/features/workbench/components/AgentInterventionDialog.tsx`
- Modify: `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`

**Requirements**:
- 弹窗仅对 agent 节点可用，参照 `NewSourceDialog` 范式
- 打开时经 `useNodeStatus` 展示当前状态，运行期订阅 SSE `/api/events/node/{id}`
- 运行态提交：先 `useNodeStop` 再 `useNodeResume`（中断+注入）
- 已结束态提交：直接 `useNodeResume`（直接发送）
- 编排进行中 pending 态并禁用重复提交

#### Checks

- [x] C3 Verify agent 节点暴露干预入口
  - Verifies: `specs/agent-intervention-web/spec.md` / Requirement "Agent 交互弹窗入口" / Scenario "agent 节点暴露干预入口"
  - Evidence: `CustomNode.tsx` 对 agent 类型节点渲染打开弹窗的触发点
  - Expect: agent 节点存在交互弹窗触发入口，非 agent 节点不渲染

- [x] C4 Verify 弹窗展示节点状态
  - Verifies: `specs/agent-intervention-web/spec.md` / Requirement "Agent 交互弹窗入口" / Scenario "弹窗展示节点状态"
  - Evidence: `AgentInterventionDialog.tsx` 调用 `useNodeStatus` 渲染当前状态
  - Expect: 弹窗打开时展示节点运行状态

- [x] C5 Verify 运行中走 stop 再 resume
  - Verifies: `specs/agent-intervention-web/spec.md` / Requirement "运行中节点中断后注入" / Scenario "运行中干预走 stop 再 resume"
  - Evidence: `AgentInterventionDialog.tsx` 在节点运行态提交时先调 `useNodeStop` 后调 `useNodeResume`
  - Expect: 运行态提交路径为 stop→resume 顺序编排

- [x] C6 Verify 编排期间禁止重复提交
  - Verifies: `specs/agent-intervention-web/spec.md` / Requirement "运行中节点中断后注入" / Scenario "编排期间禁止重复提交"
  - Evidence: 弹窗在 mutation pending 期间禁用提交按钮
  - Expect: pending 态提交按钮 disabled

- [x] C7 Verify 已结束节点直接 resume
  - Verifies: `specs/agent-intervention-web/spec.md` / Requirement "已结束节点直接发送" / Scenario "已结束节点直接 resume"
  - Evidence: `AgentInterventionDialog.tsx` 在节点非运行态提交时仅调 `useNodeResume`，不调 stop
  - Expect: 已结束态提交路径仅含 resume

- [x] C8 Verify 弹窗集成构建通过
  - Verifies: `specs/agent-intervention-web/spec.md` / Requirement "Agent 交互弹窗入口" / Scenario "agent 节点暴露干预入口"
  - Command: `cd apps/web-console && npx tsc -b && npx vite build`
  - Expect: 类型检查与构建通过
