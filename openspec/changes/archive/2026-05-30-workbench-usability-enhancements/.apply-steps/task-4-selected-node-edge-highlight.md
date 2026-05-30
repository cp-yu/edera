Task 4: Selected node edge highlight - Detailed TDD Steps

## Context

Goal: Highlight the selected Canvas node and its directly connected edges without changing runtime path semantics.

Files:
- Modify: `apps/web-console/src/features/workbench/components/Canvas.tsx`
- Test: `apps/web-console/scripts/verify-node-instance-model.mjs`

Requirements:
- Clicking a node highlights that node and all directly connected edges.
- Unrelated edges are not highlighted.
- Runtime edge colors remain authoritative when runtime state exists.
- Highlight state is derived at render time and is not persisted to DAG YAML.

Related Spec:
- `openspec/changes/workbench-usability-enhancements/specs/canvas-interaction-enhancement/spec.md`

## TDD Cycle 1: Render-derived selected neighborhood edge styling

### Step 1: Write Failing Test with complete test code

Patch `apps/web-console/scripts/verify-node-instance-model.mjs`:

1. Add a second fixture edge from `readerId` to `sinkId`:

```js
edges: [
  { from: sourceId, to: readerId, fan_in: true, fan_out: false },
  { from: readerId, to: sinkId, fan_in: false, fan_out: false },
],
```

2. Add the matching UI edge handle entry:

```js
[`e-${readerId}-${sinkId}-1`]: { sourceHandle: 'output-0', targetHandle: 'input-0' },
```

3. Add a new `verifyCanvasSelectionHighlight(cdp)` function:

```js
async function verifyCanvasSelectionHighlight(cdp) {
  const checks = await evaluate(cdp, `
    (async () => {
      const sourceNode = document.querySelector('.react-flow__node[data-id="${sourceId}"]')
      sourceNode?.dispatchEvent(clickEvent())
      await tick()
      const connected = document.querySelector('.react-flow__edge[data-id="e-${sourceId}-${readerId}-0"]')
      const unrelated = document.querySelector('.react-flow__edge[data-id="e-${readerId}-${sinkId}-1"]')
      const connectedPath = connected?.querySelector('.react-flow__edge-path')
      const connectedStroke = connectedPath ? getComputedStyle(connectedPath).stroke : ''
      const connectedWidth = Number.parseFloat(connectedPath ? getComputedStyle(connectedPath).strokeWidth : '0')
      const unrelatedPath = unrelated?.querySelector('.react-flow__edge-path')
      const unrelatedWidth = Number.parseFloat(unrelatedPath ? getComputedStyle(unrelatedPath).strokeWidth : '0')
      return {
        connectedEdgeHighlighted: connected?.classList.contains('selected-neighborhood-edge'),
        unrelatedEdgeNotHighlighted: !unrelated?.classList.contains('selected-neighborhood-edge'),
        runtimeStrokePreserved: connectedStroke === 'rgb(37, 99, 235)',
        selectedWidthIncreased: connectedWidth > unrelatedWidth,
        selectedNodeStillHighlighted: sourceNode?.classList.contains('selected'),
      }
    })()
  `)
  assertAll(checks, 'canvas selection highlight')
}
```

4. Call `await verifyCanvasSelectionHighlight(cdp)` after `verifyWorkbenchDom(cdp)` and before quick-add mutates the graph.

### Step 2: Run Test (Verify Fails) with command, expected failure, and "Test MUST fail"

Command:

```bash
npm run verify
```

Working directory:

```bash
apps/web-console
```

Expected failure: `canvas selection highlight: connectedEdgeHighlighted` fails because Canvas currently passes raw `edges` into ReactFlow without selected-neighborhood styling.

Test MUST fail.

### Step 3: Implement Minimal Code with complete implementation code

Patch `apps/web-console/src/features/workbench/components/Canvas.tsx`:

1. Include `selectedNodeId` from `useAppStore()`:

```ts
const { setInspectorTab, setSelectedEdge, setSelectedNode, entityFilter, selectedDagName, selectedNodeId } = useAppStore()
```

2. Add a render-derived `styledEdges` memo near `styledNodes`:

```ts
const styledEdges = useMemo(() => {
  if (!selectedNodeId) return edges
  return edges.map((edge) => {
    const connected = edge.source === selectedNodeId || edge.target === selectedNodeId
    if (!connected) {
      if (!edge.className?.includes('selected-neighborhood-edge')) return edge
      return {
        ...edge,
        className: edge.className?.replace(/\bselected-neighborhood-edge\b/g, '').trim() || undefined,
      }
    }
    return {
      ...edge,
      className: ['selected-neighborhood-edge', edge.className].filter(Boolean).join(' '),
      style: {
        ...(edge.style ?? {}),
        strokeWidth: Math.max(Number(edge.style?.strokeWidth ?? 2), 4),
        opacity: 1,
        filter: 'drop-shadow(0 0 5px rgba(103, 232, 249, 0.55))',
      },
    }
  })
}, [edges, selectedNodeId])
```

This must not change `edges`, `edgesRef`, `toDagDraft`, or persistence.

3. Pass `styledEdges` to React Flow:

```tsx
edges={styledEdges}
```

Do not change runtime stroke color calculation.

### Step 4: Run Test (Verify Passes) with command, expected pass, and "Test MUST pass"

Command:

```bash
npm run verify
```

Working directory:

```bash
apps/web-console
```

Expected pass: browser verification passes, connected edge gets selected-neighborhood styling, unrelated edge does not, and runtime stroke remains `rgb(37, 99, 235)`.

Test MUST pass.

### Step 5: Commit with `git add` and Conventional Commit `git commit -m`

Run:

```bash
git add apps/web-console/scripts/verify-node-instance-model.mjs apps/web-console/src/features/workbench/components/Canvas.tsx
git commit -m "feat(workbench): highlight selected node edges" -- apps/web-console/scripts/verify-node-instance-model.mjs apps/web-console/src/features/workbench/components/Canvas.tsx
```

## Summary

- Total cycles: 1
- Modified files:
  - `apps/web-console/scripts/verify-node-instance-model.mjs`
  - `apps/web-console/src/features/workbench/components/Canvas.tsx`
- Commit count: 1
