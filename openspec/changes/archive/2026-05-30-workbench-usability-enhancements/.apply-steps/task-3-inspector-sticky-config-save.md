Task 3: Inspector sticky config save - Detailed TDD Steps

## Context

Goal: Keep the Config tab instance save action visible at the bottom of the Inspector viewport.

Files:
- Modify: `apps/web-console/src/features/workbench/components/Inspector.tsx`
- Test: `apps/web-console/scripts/verify-node-instance-model.mjs`

Requirements:
- Inspector Config tab uses a layout with scrollable form content and fixed visible save footer.
- Runtime and Triggers tabs do not display the Config save footer.
- Existing `save()` behavior and `useSaveDag` payload remain unchanged.

Related Spec:
- `openspec/changes/workbench-usability-enhancements/specs/dag-workbench-ui/spec.md`

## TDD Cycle 1: Sticky Config save footer

### Step 1: Write Failing Test with complete test code

Patch `apps/web-console/scripts/verify-node-instance-model.mjs` in `verifyInspector(cdp)`.

After the `nodeInspector` assertion, add:

```js
  const configFooter = await evaluate(cdp, `
    (() => {
      const aside = [...document.querySelectorAll('aside')].at(-1)
      const footer = aside?.querySelector('[data-inspector-config-footer]')
      const saveButton = footer?.querySelector('button')
      const footerStyle = footer ? getComputedStyle(footer) : null
      return {
        footerExists: Boolean(footer),
        footerSticky: footerStyle?.position === 'sticky',
        saveButtonVisible: saveButton?.textContent.includes('保存实例'),
      }
    })()
  `)
  assertAll(configFooter, 'inspector config footer')
```

Then switch to Runtime and Triggers tabs and assert the footer is absent:

```js
  const nonConfigFooter = await evaluate(cdp, `
    (async () => {
      const aside = [...document.querySelectorAll('aside')].at(-1)
      const clickTab = async (label) => {
        ;[...aside.querySelectorAll('button')].find((button) => button.textContent.includes(label))?.click()
        await tick()
        return Boolean(aside.querySelector('[data-inspector-config-footer]'))
      }
      const runtimeHasFooter = await clickTab('Runtime')
      const triggersHasFooter = await clickTab('Triggers')
      ;[...aside.querySelectorAll('button')].find((button) => button.textContent.includes('Config'))?.click()
      await tick()
      return {
        runtimeFooterAbsent: runtimeHasFooter === false,
        triggersFooterAbsent: triggersHasFooter === false,
      }
    })()
  `)
  assertAll(nonConfigFooter, 'inspector non-config footer')
```

Keep the existing save payload assertion intact.

### Step 2: Run Test (Verify Fails) with command, expected failure, and "Test MUST fail"

Command:

```bash
npm run verify
```

Working directory:

```bash
apps/web-console
```

Expected failure: `inspector config footer: footerExists` and/or `footerSticky` fails because the save button is currently rendered inline at the end of the scrollable Inspector content.

Test MUST fail.

### Step 3: Implement Minimal Code with complete implementation code

Patch the selected-node branch in `apps/web-console/src/features/workbench/components/Inspector.tsx`:

1. Change the selected-node aside from a single scrolling stack:

```tsx
<aside className="w-[300px] space-y-4 overflow-y-auto border-l bg-card p-4">
```

to a panel that owns a scrollable body:

```tsx
<aside className="flex h-full w-[300px] flex-col border-l bg-card">
```

2. Wrap the header, tabs, and active tab content in an inner body:

```tsx
<div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
  ...
</div>
```

3. In the Config branch, render fields in normal content and move only the save button into a sticky footer:

```tsx
<>
  <div className="space-y-4">
    <Field label="Alias" value={alias} onChange={setAlias} />
    <Readonly label="类型" value={node.type_name} />
    <Readonly label="角色" value={node.role} />
    <Readonly label="输入" value={node.input_type} />
    <Readonly label="输出" value={node.output_type} />
    <SchemaForm ... />
    <EntitySelector ... />
    <PermissionConfigurator ... />
  </div>
  <div data-inspector-config-footer className="sticky bottom-0 -mx-4 mt-4 border-t bg-card p-4">
    <button ...>
      {saveDag.isPending ? '保存中...' : '保存实例'}
    </button>
  </div>
</>
```

Keep the existing `save` function and the button `onClick`, `disabled`, and mutation payload unchanged.

Runtime and Triggers branches must remain inside the body and must not render `[data-inspector-config-footer]`.

### Step 4: Run Test (Verify Passes) with command, expected pass, and "Test MUST pass"

Command:

```bash
npm run verify
```

Working directory:

```bash
apps/web-console
```

Expected pass: browser verification passes, the Config footer is sticky, Runtime/Triggers have no instance save footer, and the existing save payload assertion still passes.

Test MUST pass.

### Step 5: Commit with `git add` and Conventional Commit `git commit -m`

Run:

```bash
git add apps/web-console/scripts/verify-node-instance-model.mjs apps/web-console/src/features/workbench/components/Inspector.tsx
git commit -m "feat(workbench): keep inspector save visible" -- apps/web-console/scripts/verify-node-instance-model.mjs apps/web-console/src/features/workbench/components/Inspector.tsx
```

## Summary

- Total cycles: 1
- Modified files:
  - `apps/web-console/scripts/verify-node-instance-model.mjs`
  - `apps/web-console/src/features/workbench/components/Inspector.tsx`
- Commit count: 1
