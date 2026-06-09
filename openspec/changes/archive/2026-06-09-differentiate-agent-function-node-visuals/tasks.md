### Task 1: Type-driven 节点视觉 [x]

**Goal**: 将 Workbench Canvas 节点视觉从 legacy kind 迁移到 `node.type` 驱动的视觉家族。

**Files**:
- Modify: `apps/web-console/src/features/workbench/lib/graph.ts`
- Modify: `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`
- Modify: `apps/web-console/src/features/workbench/components/Canvas.tsx`

**Requirements**:
- `NodeKind` 使用 `function | agent | dag | wait | unknown`。
- `getNodeKind` 从 `node.type` 推导 visual kind，不从 `role` 推导视觉家族。
- `CustomNode.tsx` 为新 visual kind 提供不同图标、配色和卡片样式。
- `Canvas.tsx` 只消费 `getNodeSize` 与 `getNodeEdgeColor`，不直接分支 agent/function。
- agent intervention 按钮继续保留在 agent 节点上。

#### Checks

- [x] C1 Verify function 与 agent 视觉差异
  - Verifies: `specs/node-visual-system/spec.md` / Requirement "Type-differentiated node appearance" / Scenario "Function node style", "Agent node style", "Role does not change visual family"
  - Command: `cd apps/web-console && npm run verify`
  - Expect: verification 覆盖 function 与 agent 在 source / processor / sink role 下的 `getNodeKind` 映射，且两者 visual kind 不同

- [x] C2 Verify dag 与 wait 视觉家族
  - Verifies: `specs/node-visual-system/spec.md` / Requirement "Type-differentiated node appearance" / Scenario "DAG node style", "Wait node style"
  - Command: `cd apps/web-console && npm run verify`
  - Expect: verification 覆盖 `type: dag` 与 `type: wait` 的 visual kind 映射

- [x] C3 Verify agent intervention 保留
  - Verifies: `specs/node-visual-system/spec.md` / Requirement "Type-differentiated node appearance" / Scenario "Agent intervention remains available"
  - Evidence: `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`
  - Expect: agent intervention 入口仍由 `node.type === 'agent'` 控制

### Task 2: Role-driven Handle 回归 [x]

**Goal**: 确认视觉迁移不改变 Handle 拓扑和 Palette role 分组边界。

**Files**:
- Modify: `apps/web-console/src/features/workbench/lib/graph.ts`
- Test: `apps/web-console/scripts/verify-node-instance-model.mjs`

**Requirements**:
- `getHandleSpecs` 继续只根据 `role` 与连接关系生成输入/输出 Handle。
- source 节点仅输出，sink 节点仅输入，processor 节点两侧均可生成 Handle。
- function 与 agent 在相同 role 和连接关系下生成相同 Handle 拓扑。
- 不修改 `apps/web-console/src/features/workbench/components/Palette.tsx`。
- 不修改后端 schema 或 service common 文件。

#### Checks

- [x] C4 Verify Handle 拓扑仍由 role 驱动
  - Verifies: `specs/node-visual-system/spec.md` / Requirement "Dynamic handle generation" / Scenario "Source node handle generation", "Sink node handle generation", "Processor handle count follows connectivity", "Handle topology remains role-driven"
  - Command: `cd apps/web-console && npm run verify`
  - Expect: verification 覆盖 source / processor / sink role 的 Handle 规则，并证明 function 与 agent 在相同 role 下 Handle 拓扑一致

- [x] C5 Verify 边界文件未被修改
  - Verifies: `specs/node-visual-system/spec.md` / Requirement "Dynamic handle generation" / Scenario "Handle topology remains role-driven"
  - Command: `git diff -- apps/web-console/src/features/workbench/components/Palette.tsx packages/core/src/edera_core/models/schema.py packages/core/src/edera_core/service_common.py`
  - Expect: command 输出为空
