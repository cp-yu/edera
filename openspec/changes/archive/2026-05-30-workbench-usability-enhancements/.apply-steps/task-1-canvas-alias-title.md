Task 1: Canvas alias title - Detailed TDD Steps

## Context

Goal: Make Canvas node cards show instance alias as the primary title while preserving type context.

Files:
- Modify: `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`
- Test: `apps/web-console/scripts/verify-node-instance-model.mjs`

Requirements:
- Canvas node title uses `alias || type_name`.
- Canvas node card keeps `type_name` visible as secondary context.
- Alias display does not change persisted node identity or edge references.

Related Spec:
- `openspec/changes/workbench-usability-enhancements/specs/node-visual-system/spec.md`

## TDD Cycle 1: Alias-first Canvas title

### Step 1: Write Failing Test with complete test code

Patch `apps/web-console/scripts/verify-node-instance-model.mjs` in `verifyWorkbenchDom(cdp)` so the returned checks include alias-first title assertions:

```js
const titleText = readerNode?.querySelector('[data-node-title]')?.textContent?.trim()
const typeContext = readerNode?.querySelector('[data-node-type-context]')?.textContent?.trim()
```

Add these checks to the object returned by `verifyWorkbenchDom`:

```js
aliasPrimaryTitle: titleText === 'market-reader',
typeContextPreserved: typeContext === 'reader',
identityTextNotPrimaryTitle: titleText !== readerId,
```

Do not change fixture node IDs or edge fixtures.

### Step 2: Run Test (Verify Fails) with command, expected failure, and "Test MUST fail"

Command:

```bash
npm run verify
```

Working directory:

```bash
apps/web-console
```

Expected failure: `aliasPrimaryTitle` and/or `typeContextPreserved` fails because `CustomNode` has no `[data-node-title]`/`[data-node-type-context]` elements and still emphasizes the type/name layout.

Test MUST fail.

### Step 3: Implement Minimal Code with complete implementation code

Patch `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`:

1. After `entityBorderColor`, define:

```ts
const title = node.alias || node.type_name
```

2. Keep the header visually as type context, but add the data marker:

```tsx
<span data-node-type-context className="min-w-0 flex-1 truncate">{node.type_name}</span>
```

3. Change the primary body title from `node.name` to alias-first:

```tsx
<div data-node-title className="pr-4 text-sm font-semibold">{title}</div>
```

No persistence, ID, edge, or graph conversion code should change in this cycle.

### Step 4: Run Test (Verify Passes) with command, expected pass, and "Test MUST pass"

Command:

```bash
npm run verify
```

Working directory:

```bash
apps/web-console
```

Expected pass: browser verification passes, including alias-first title and preserved type context.

Test MUST pass.

### Step 5: Commit with `git add` and Conventional Commit `git commit -m`

Run:

```bash
git add apps/web-console/scripts/verify-node-instance-model.mjs apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx
git commit -m "feat(workbench): show node alias on canvas" -- apps/web-console/scripts/verify-node-instance-model.mjs apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx
```

## Summary

- Total cycles: 1
- Modified files:
  - `apps/web-console/scripts/verify-node-instance-model.mjs`
  - `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`
- Commit count: 1
