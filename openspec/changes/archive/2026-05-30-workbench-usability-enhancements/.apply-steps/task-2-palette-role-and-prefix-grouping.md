Task 2: Palette role and prefix grouping - Detailed TDD Steps

## Context

Goal: Keep role grouping in Palette and add deterministic prefix subgroups.

Files:
- Modify: `apps/web-console/src/features/workbench/components/Palette.tsx`
- Test: `apps/web-console/scripts/verify-node-instance-model.mjs`

Requirements:
- Palette groups prototypes first by `role`.
- Palette groups prototypes within each role by deterministic name prefix.
- Drag payload remains the original `node.name`.

Related Spec:
- `openspec/changes/workbench-usability-enhancements/specs/dag-workbench-ui/spec.md`

## TDD Cycle 1: Prefix subgroups under role groups

### Step 1: Write Failing Test with complete test code

Patch `apps/web-console/scripts/verify-node-instance-model.mjs`:

1. Add more source prototypes to `fixtures.nodeTypes` so a role contains multiple deterministic prefixes:

```js
nodeType('uzi-fetch-price', 'function', 'source', 'Any', 'PriceTick', {
  handler: 'fetch-price',
}),
nodeType('uzi-render-chart', 'function', 'source', 'Any', 'ChartSpec', {
  handler: 'render-chart',
}),
```

Place them after `rss-fetcher`.

2. Add a new function after `verifyQuickAddAndMultiInstance(cdp)`:

```js
async function verifyPaletteGrouping(cdp) {
  const checks = await evaluate(cdp, `
    (() => {
      const palette = document.querySelector('aside')
      const text = palette?.textContent ?? ''
      const sourceRole = text.includes('Source 节点')
      const processorRole = text.includes('Processor 节点')
      const sinkRole = text.includes('Sink 节点')
      const uziFetchGroup = text.includes('uzi-fetch')
      const uziRenderGroup = text.includes('uzi-render')
      const dragNode = [...(palette?.querySelectorAll('[draggable="true"]') ?? [])]
        .find((item) => item.textContent.includes('uzi-fetch-price'))
      const event = new DragEvent('dragstart', { bubbles: true, cancelable: true, dataTransfer: new DataTransfer() })
      dragNode?.dispatchEvent(event)
      return {
        sourceRole,
        processorRole,
        sinkRole,
        uziFetchGroup,
        uziRenderGroup,
        dragPayloadUnchanged: event.dataTransfer.getData('application/reactflow') === 'uzi-fetch-price',
      }
    })()
  `)
  assertAll(checks, 'palette grouping')
}
```

3. Call `await verifyPaletteGrouping(cdp)` in `main()` after `verifyQuickAddAndMultiInstance(cdp)`.

### Step 2: Run Test (Verify Fails) with command, expected failure, and "Test MUST fail"

Command:

```bash
npm run verify
```

Working directory:

```bash
apps/web-console
```

Expected failure: `palette grouping: uziFetchGroup` and/or `palette grouping: uziRenderGroup` fails because Palette currently renders only role groups and flat node items.

Test MUST fail.

### Step 3: Implement Minimal Code with complete implementation code

Patch `apps/web-console/src/features/workbench/components/Palette.tsx`:

1. Add these helpers above `Palette()`:

```ts
type Prototype = NonNullable<ReturnType<typeof useNodePrototypes>['data']>['prototypes'][number]

const ROLE_LABELS = {
  source: 'Source 节点',
  processor: 'Processor 节点',
  sink: 'Sink 节点',
} as const

const ROLE_ORDER = ['source', 'processor', 'sink'] as const

function prefixOf(name: string): string {
  const parts = name.split('-').filter(Boolean)
  if (parts[0] === 'uzi' && parts.length >= 2) return `${parts[0]}-${parts[1]}`
  return parts[0] ?? name
}

function groupPrototypes(prototypes: Prototype[]) {
  const grouped = new Map<string, Map<string, Prototype[]>>()

  for (const node of prototypes) {
    const role = node.role
    const prefix = prefixOf(node.name)
    const roleGroup = grouped.get(role) ?? new Map<string, Prototype[]>()
    const prefixGroup = roleGroup.get(prefix) ?? []
    prefixGroup.push(node)
    roleGroup.set(prefix, prefixGroup)
    grouped.set(role, roleGroup)
  }

  return ROLE_ORDER.flatMap((role) => {
    const roleGroup = grouped.get(role)
    if (!roleGroup) return []
    return [{
      role,
      label: ROLE_LABELS[role],
      prefixes: Array.from(roleGroup.entries())
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([prefix, nodes]) => ({
          prefix,
          nodes: nodes.slice().sort((left, right) => left.name.localeCompare(right.name)),
        })),
    }]
  })
}
```

2. Replace the current flat `reduce<Record<string, typeof prototypes>>` grouping with:

```ts
const grouped = groupPrototypes(prototypes)
```

3. Render role groups, then nested prefix groups, preserving the drag payload:

```tsx
{grouped.map((group) => (
  <div key={group.role}>
    <h3 className="mb-2 text-xs font-medium text-muted-foreground">{group.label}</h3>
    <div className="space-y-3">
      {group.prefixes.map((prefixGroup) => (
        <div key={prefixGroup.prefix} className="space-y-1">
          <div className="text-[11px] font-medium text-muted-foreground">{prefixGroup.prefix}</div>
          {prefixGroup.nodes.map((node) => (
            <div
              key={node.name}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('application/reactflow', node.name)
                e.dataTransfer.effectAllowed = 'move'
              }}
              className="cursor-grab rounded-md border px-3 py-2 text-sm transition-colors hover:bg-accent/50"
            >
              {node.name}
            </div>
          ))}
        </div>
      ))}
    </div>
  </div>
))}
```

Do not modify DAG creation or drag/drop code.

### Step 4: Run Test (Verify Passes) with command, expected pass, and "Test MUST pass"

Command:

```bash
npm run verify
```

Working directory:

```bash
apps/web-console
```

Expected pass: browser verification passes, including role labels, prefix labels, and unchanged `application/reactflow` payload.

Test MUST pass.

### Step 5: Commit with `git add` and Conventional Commit `git commit -m`

Run:

```bash
git add apps/web-console/scripts/verify-node-instance-model.mjs apps/web-console/src/features/workbench/components/Palette.tsx
git commit -m "feat(workbench): group palette nodes by prefix" -- apps/web-console/scripts/verify-node-instance-model.mjs apps/web-console/src/features/workbench/components/Palette.tsx
```

## Summary

- Total cycles: 1
- Modified files:
  - `apps/web-console/scripts/verify-node-instance-model.mjs`
  - `apps/web-console/src/features/workbench/components/Palette.tsx`
- Commit count: 1
