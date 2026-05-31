### Task 1: Persist selected DAG

**Goal**: Restore the last selected DAG when the user opens Workbench.

**Files**:
- Modify: `apps/web-console/src/store/useAppStore.ts`
- Test: `apps/web-console/tests/workbench-usability.spec.ts`

**Requirements**:
- Initialize `selectedDagName` from `localStorage['workbench:selectedDagName']`, falling back to `default`.
- Write the same key in `setSelectedDag`.
- Preserve existing selection reset behavior when switching DAG.
- Do not add backend API or URL query state.

#### Checks

- [x] C1 Verify selected DAG persistence
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "DAG selector and switching" / Scenario "Persist selected DAG"
  - Command: `npx playwright test apps/web-console/tests/workbench-usability.spec.ts`
  - Expect: selecting DAG `analysis` stores it as the Workbench last selected DAG

- [x] C2 Verify selected DAG restore
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "DAG selector and switching" / Scenario "Restore last selected DAG"
  - Command: `npx playwright test apps/web-console/tests/workbench-usability.spec.ts`
  - Expect: opening `/workbench` with stored DAG `analysis` loads and displays DAG `analysis`

### Task 2: Add Palette search

**Goal**: Let users filter the node Palette by node type name or current DAG instance alias.

**Files**:
- Modify: `apps/web-console/src/features/workbench/WorkbenchPage.tsx`
- Modify: `apps/web-console/src/features/workbench/components/Palette.tsx`
- Test: `apps/web-console/tests/workbench-usability.spec.ts`

**Requirements**:
- Pass current DAG data from `WorkbenchPage` to `Palette`.
- Add a Palette search input.
- Match search text against node type names.
- Match search text against aliases of current DAG instances whose type maps to that prototype.
- Preserve drag payload `application/reactflow = node.name`.

#### Checks

- [x] C3 Verify Palette type-name search
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node palette with drag-to-add" / Scenario "Search matches type name and instance alias"
  - Command: `npx playwright test apps/web-console/tests/workbench-usability.spec.ts`
  - Expect: searching by node type name shows matching node types and hides non-matches

- [x] C4 Verify Palette alias search
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node palette with drag-to-add" / Scenario "Search matches type name and instance alias"
  - Command: `npx playwright test apps/web-console/tests/workbench-usability.spec.ts`
  - Expect: searching by current DAG instance alias shows that instance's node type in the Palette

### Task 3: Add Palette collapse

**Goal**: Let users collapse Palette role and prefix groups without persisting that state.

**Files**:
- Modify: `apps/web-console/src/features/workbench/components/Palette.tsx`
- Test: `apps/web-console/tests/workbench-usability.spec.ts`

**Requirements**:
- Add collapse controls for role groups.
- Add collapse controls for prefix groups.
- Store collapse state only in Palette component state.
- Restore default expanded state after page reload or remount.
- Ensure active search results are visible even if their group was previously collapsed.

#### Checks

- [x] C5 Verify group collapse
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node palette with drag-to-add" / Scenario "Collapse palette group"
  - Command: `npx playwright test apps/web-console/tests/workbench-usability.spec.ts`
  - Expect: collapsing a Palette group hides that group's node type list

- [x] C6 Verify collapse is session-local
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node palette with drag-to-add" / Scenario "Palette collapse state is session-local"
  - Command: `npx playwright test apps/web-console/tests/workbench-usability.spec.ts`
  - Expect: reloading Workbench restores Palette groups to the default expanded state

- [x] C7 Verify search bypasses collapsed groups
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node palette with drag-to-add" / Scenario "Search shows matching groups"
  - Command: `npx playwright test apps/web-console/tests/workbench-usability.spec.ts`
  - Expect: a matching node type remains visible while search is active even if its group was collapsed

### Task 4: Strengthen selected-node edge contrast

**Goal**: Make a selected node's one-hop edges stand out while dimming unrelated edges.

**Files**:
- Modify: `apps/web-console/src/features/workbench/components/Canvas.tsx`
- Test: `apps/web-console/tests/workbench-usability.spec.ts`

**Requirements**:
- Keep selected node connected edges highlighted with width, opacity, class, or shadow.
- Lower opacity for edges not directly connected to `selectedNodeId`.
- Do not change edge stroke color when runtime path coloring is present.
- Keep the visual state derived from React render state only.

#### Checks

- [x] C8 Verify connected edges are highlighted
  - Verifies: `specs/canvas-interaction-enhancement/spec.md` / Requirement "Selected node neighborhood highlight" / Scenario "Highlight connected edges on node click"
  - Command: `npx playwright test apps/web-console/tests/workbench-usability.spec.ts`
  - Expect: clicking node B in an A -> B -> C graph highlights A -> B and B -> C

- [x] C9 Verify unrelated edges are de-emphasized
  - Verifies: `specs/canvas-interaction-enhancement/spec.md` / Requirement "Selected node neighborhood highlight" / Scenario "De-emphasize unrelated edges"
  - Command: `npx playwright test apps/web-console/tests/workbench-usability.spec.ts`
  - Expect: clicking node B lowers opacity for an edge not connected to B

- [x] C10 Verify runtime color remains
  - Verifies: `specs/canvas-interaction-enhancement/spec.md` / Requirement "Selected node neighborhood highlight" / Scenario "Selection highlight does not override runtime path color"
  - Command: `npx playwright test apps/web-console/tests/workbench-usability.spec.ts`
  - Expect: selected-node styling does not replace runtime edge stroke color
