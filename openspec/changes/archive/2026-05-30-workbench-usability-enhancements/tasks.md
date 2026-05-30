### Task 1: Canvas alias title

**Goal**: Make Canvas node cards show instance alias as the primary title while preserving type context.

**Files**:
- Modify: `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`
- Modify: `apps/web-console/src/features/workbench/lib/graph.ts`
- Test: `apps/web-console/scripts/verify-node-instance-model.mjs`

**Requirements**:
- Canvas node title uses `alias || type_name`.
- Canvas node card keeps `type_name` visible as secondary context.
- Alias display does not change persisted node identity or edge references.

#### Checks

- [x] C1 Verify alias-first Canvas title
  - Verifies: `specs/node-visual-system/spec.md` / Requirement "Alias-first Canvas node title" / Scenario "Canvas title uses alias"
  - Evidence: `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`
  - Expect: node title expression prefers `alias` and secondary text includes `type_name`

- [x] C2 Verify title fallback and identity preservation
  - Verifies: `specs/node-visual-system/spec.md` / Requirement "Alias-first Canvas node title" / Scenario "Canvas title falls back to type_name", "Alias display does not change identity"
  - Command: `npm run verify`
  - Expect: node instance model verification passes and saved edges still use instance UUIDs

### Task 2: Palette role and prefix grouping

**Goal**: Keep role grouping in Palette and add deterministic prefix subgroups.

**Files**:
- Modify: `apps/web-console/src/features/workbench/components/Palette.tsx`
- Modify: `apps/web-console/src/features/workbench/lib/graph.ts`
- Test: `apps/web-console/src/features/workbench/components/Palette.tsx`

**Requirements**:
- Palette groups prototypes first by `role`.
- Palette groups prototypes within each role by deterministic name prefix.
- Drag payload remains the original `node.name`.

#### Checks

- [x] C3 Verify role and prefix grouping
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node palette with drag-to-add" / Scenario "Grouped display by role and prefix"
  - Evidence: `apps/web-console/src/features/workbench/components/Palette.tsx`
  - Expect: Palette rendering nests prefix groups under each role group

- [x] C4 Verify drag-to-add payload is unchanged
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node palette with drag-to-add" / Scenario "Drag to create instance", "Multiple instances of same type"
  - Evidence: `apps/web-console/src/features/workbench/components/Palette.tsx`
  - Expect: `onDragStart` still writes `node.name` to `application/reactflow`

### Task 3: Inspector sticky config save

**Goal**: Keep the Config tab instance save action visible at the bottom of the Inspector viewport.

**Files**:
- Modify: `apps/web-console/src/features/workbench/components/Inspector.tsx`
- Test: `apps/web-console/src/features/workbench/components/Inspector.tsx`

**Requirements**:
- Inspector Config tab uses a layout with scrollable form content and fixed visible save footer.
- Runtime and Triggers tabs do not display the Config save footer.
- Existing `save()` behavior and `useSaveDag` payload remain unchanged.

#### Checks

- [x] C5 Verify Config save remains visible
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node inspector with editable/readonly fields" / Scenario "Config save remains visible"
  - Evidence: `apps/web-console/src/features/workbench/components/Inspector.tsx`
  - Expect: Config tab renders the save action in a sticky or fixed footer within the Inspector panel

- [x] C6 Verify non-config tabs do not show save footer
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node inspector with editable/readonly fields" / Scenario "Non-config tabs do not show instance save footer"
  - Evidence: `apps/web-console/src/features/workbench/components/Inspector.tsx`
  - Expect: Runtime and Triggers branches do not render the instance save footer

### Task 4: Selected node edge highlight

**Goal**: Highlight the selected Canvas node and its directly connected edges without changing runtime path semantics.

**Files**:
- Modify: `apps/web-console/src/features/workbench/components/Canvas.tsx`
- Modify: `apps/web-console/src/store/useAppStore.ts`
- Test: `apps/web-console/src/features/workbench/components/Canvas.tsx`

**Requirements**:
- Clicking a node highlights that node and all directly connected edges.
- Unrelated edges are not highlighted.
- Runtime edge colors remain authoritative when runtime state exists.
- Highlight state is derived at render time and is not persisted to DAG YAML.

#### Checks

- [x] C7 Verify connected edges highlight on node click
  - Verifies: `specs/canvas-interaction-enhancement/spec.md` / Requirement "Selected node neighborhood highlight" / Scenario "Highlight connected edges on node click"
  - Evidence: `apps/web-console/src/features/workbench/components/Canvas.tsx`
  - Expect: edges with `source` or `target` equal to `selectedNodeId` receive additional selected-neighborhood styling

- [x] C8 Verify unrelated edges and runtime color behavior
  - Verifies: `specs/canvas-interaction-enhancement/spec.md` / Requirement "Selected node neighborhood highlight" / Scenario "Do not highlight unrelated edges", "Selection highlight does not override runtime path color"
  - Evidence: `apps/web-console/src/features/workbench/components/Canvas.tsx`
  - Expect: unrelated edges remain unhighlighted and runtime edge color calculation is preserved

## Remediation

- [x] [code_fix] Add missing Inspector readonly `name` field required by `Node inspector with editable/readonly fields`.
