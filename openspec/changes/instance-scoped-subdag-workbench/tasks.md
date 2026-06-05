### Task 1: Graph payload preserves sub-DAG instance fields

**Goal**: 保证 Workbench 读取和保存 DAG 时不会丢失 sub-DAG 实例字段。

**Files**:
- Modify: `packages/core/src/edera_core/service_common.py`
- Modify: `packages/core/src/edera_core/graph_service.py`
- Modify: `apps/web-console/src/api/types.ts`
- Modify: `apps/web-console/src/features/workbench/lib/graph.ts`
- Test: `packages/core/tests/test_graph_service.py`
- Test: `apps/web-console/scripts/verify-node-instance-model.mjs`

**Requirements**:
- GraphService GET/SAVE response 保留 `dag_ref/input_mapping`。
- `DagNodeRecord` 和 `NodeInstance` 类型显式支持 sub-DAG 字段。
- `toDagDraft()` 保留 sub-DAG 实例字段。
- 后端保存 payload 校验后仍保留字段。

#### Checks

- [ ] C1 Verify sub-DAG graph round-trip
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService DAG CRUD" / Scenario "sub-DAG instance round-trip"
  - Command: `uv run pytest packages/core/tests/test_graph_service.py`
  - Expect: graph service test proves `dag_ref` and `input_mapping` survive GET/SAVE

- [ ] C2 Verify Workbench draft serialization
  - Verifies: `specs/node-instance-model/spec.md` / Requirement "Sub-DAG instance fields" / Scenario "Preserve sub-DAG instance fields in draft save"
  - Command: `npm --prefix apps/web-console run verify`
  - Expect: web console verification covers `toDagDraft()` preserving `dag_ref/input_mapping`

### Task 2: DAG entries in Workbench palette

**Goal**: 将 DAG Entity 暴露为左侧节点面板可拖入候选，并创建正确的 sub-DAG 节点实例。

**Files**:
- Modify: `apps/web-console/src/api/queries.ts`
- Modify: `apps/web-console/src/features/workbench/components/Palette.tsx`
- Modify: `apps/web-console/src/features/workbench/components/QuickAddPanel.tsx`
- Modify: `apps/web-console/src/features/workbench/components/Canvas.tsx`
- Test: `apps/web-console/tests/workbench-usability.spec.ts`

**Requirements**:
- Palette 获取 DAG 列表并展示独立 DAG 分组。
- 当前根 DAG 不作为可拖入 DAG 候选。
- 拖入 DAG 候选时创建 `type: "dag"`、`dag_ref` 指向目标 DAG 的实例。
- Quick add 搜索行为与 Palette 保持一致。

#### Checks

- [ ] C3 Verify DAG palette entries
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "DAG palette entries" / Scenario "DAG appears in palette"
  - Command: `npm --prefix apps/web-console exec playwright test tests/workbench-usability.spec.ts`
  - Expect: Workbench shows existing DAG as a distinct palette candidate

- [ ] C4 Verify DAG drag creates sub-DAG instance
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "DAG palette entries" / Scenario "Drag DAG into canvas"
  - Command: `npm --prefix apps/web-console exec playwright test tests/workbench-usability.spec.ts`
  - Expect: drag/drop saves node instance with `type: "dag"` and `dag_ref`

### Task 3: Instance-scoped sub-DAG navigation

**Goal**: 右键 sub-DAG 节点进入目标 DAG，并保留父节点实例上下文和返回路径。

**Files**:
- Modify: `apps/web-console/src/store/useAppStore.ts`
- Modify: `apps/web-console/src/features/workbench/WorkbenchPage.tsx`
- Modify: `apps/web-console/src/features/workbench/components/Canvas.tsx`
- Modify: `apps/web-console/src/features/workbench/components/CanvasContextMenu.tsx`
- Test: `apps/web-console/tests/workbench-usability.spec.ts`

**Requirements**:
- 仅 sub-DAG 节点显示“进入 Sub DAG”右键菜单项。
- 进入行为使用被点击的节点实例作为父上下文。
- sub-DAG 视图渲染目标 DAG，但不覆盖根 `selectedDagName`。
- 提供返回父 DAG 的导航。

#### Checks

- [ ] C5 Verify context menu entry
  - Verifies: `specs/canvas-interaction-enhancement/spec.md` / Requirement "Sub-DAG node context menu entry" / Scenario "Show enter action for sub-DAG node"
  - Command: `npm --prefix apps/web-console exec playwright test tests/workbench-usability.spec.ts`
  - Expect: sub-DAG node context menu contains enter action and regular nodes do not

- [ ] C6 Verify instance-scoped navigation
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Instance-scoped sub-DAG navigation" / Scenario "Enter sub-DAG view"
  - Command: `npm --prefix apps/web-console exec playwright test tests/workbench-usability.spec.ts`
  - Expect: entering sub-DAG renders child DAG while preserving parent context

### Task 4: Run-scoped runtime status

**Goal**: 支持按 `run_id` 查询 runtime status，并让 sub-DAG 视图只消费对应 child run 的状态。

**Files**:
- Modify: `proto/edera.proto`
- Modify: `packages/core/src/edera_core/grpc_client.py`
- Modify: `packages/core/src/edera_core/graph_service.py`
- Modify: `packages/core/src/edera_core/web/routes.py`
- Modify: `apps/web-console/src/api/queries.ts`
- Modify: `apps/web-console/src/features/workbench/WorkbenchPage.tsx`
- Modify: `apps/web-console/src/features/workbench/components/Inspector.tsx`
- Test: `packages/core/tests/test_graph_service.py`
- Test: `packages/core/tests/test_web_routes.py`

**Requirements**:
- Runtime status 无 `run_id` 时保持既有最近 run 行为。
- Runtime status 带 `run_id` 时只返回指定 run 的 node runs。
- Workbench sub-DAG 视图从父节点 metadata 解析 `sub_dag_run_id`。
- Canvas 和 Inspector Runtime 使用 child `run_id` 的状态、输出和日志。
- 无 child run 时显示空态，不 fallback 到同名 DAG 最近 run。

#### Checks

- [ ] C7 Verify run-scoped runtime status API
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService runtime-status" / Scenario "查询指定 run runtime status"
  - Command: `uv run pytest packages/core/tests/test_graph_service.py packages/core/tests/test_web_routes.py`
  - Expect: API returns statuses only for requested `run_id`

- [ ] C8 Verify no sibling status leakage
  - Verifies: `specs/dag-run-observability/spec.md` / Requirement "Instance-scoped sub-DAG runtime view" / Scenario "Do not leak sibling parent status"
  - Command: `npm --prefix apps/web-console exec playwright test tests/workbench-usability.spec.ts`
  - Expect: entering `dagA.nodeX` sub-DAG view does not show `dagB.nodeY` child run status

### Task 5: Parent instance to child run lookup

**Goal**: 确保父节点实例可稳定解析到对应 child DAG run，供 Workbench 实例作用域导航使用。

**Files**:
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Modify: `packages/core/src/edera_core/query_service.py`
- Modify: `packages/core/src/edera_core/web/routes.py`
- Modify: `apps/web-console/src/api/queries.ts`
- Test: `packages/core/tests/test_query_service.py`
- Test: `packages/core/tests/test_web_routes.py`

**Requirements**:
- 父节点运行记录或输出 metadata 包含 child run 标识。
- 查询接口可通过父 run 和父节点实例获取 child run。
- 多个父实例引用同一 `dag_ref` 时 lookup 不合并。
- 未执行过的实例返回空结果。

#### Checks

- [ ] C9 Verify parent instance child run lookup
  - Verifies: `specs/sub-dag-execution/spec.md` / Requirement "Parent instance to child run association" / Scenario "Parent node records child run"
  - Command: `uv run pytest packages/core/tests/test_query_service.py packages/core/tests/test_web_routes.py`
  - Expect: lookup returns the child run associated with the requested parent node instance

- [ ] C10 Verify unexecuted sub-DAG empty state
  - Verifies: `specs/dag-run-observability/spec.md` / Requirement "Instance-scoped sub-DAG runtime view" / Scenario "No child run yet"
  - Command: `npm --prefix apps/web-console exec playwright test tests/workbench-usability.spec.ts`
  - Expect: Workbench shows no-child-run empty state and does not fallback to latest same-name DAG run
