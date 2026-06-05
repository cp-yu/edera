import { expect, test, type Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await mockWorkbench(page)
})

test('persists selected DAG', async ({ page }) => {
  await page.goto('/workbench')

  await page.locator('select').first().selectOption('analysis')

  await expect.poll(() => page.evaluate(() => localStorage.getItem('workbench:selectedDagName'))).toBe('analysis')
  await expect(page.locator('select').first()).toHaveValue('analysis')
})

test('restores last selected DAG', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('workbench:selectedDagName', 'analysis'))

  await page.goto('/workbench')

  await expect(page.locator('select').first()).toHaveValue('analysis')
  await expect(page.locator('.react-flow__node').filter({ hasText: 'Market Alpha' })).toBeVisible()
})

test('filters Palette by type name and current DAG alias', async ({ page }) => {
  await page.goto('/workbench')
  await page.locator('select').first().selectOption('analysis')
  const palette = palettePanel(page)

  await palette.getByLabel('搜索节点').fill('processor')
  await expect(palette.getByText('processor-transform', { exact: true })).toBeVisible()
  await expect(palette.getByText('source-alpha', { exact: true })).toHaveCount(0)

  await palette.getByLabel('搜索节点').fill('Market Alpha')
  await expect(palette.getByText('source-alpha', { exact: true })).toBeVisible()
  await expect(palette.getByText('processor-transform', { exact: true })).toHaveCount(0)
})

test('collapses Palette groups only for the current page session', async ({ page }) => {
  await page.goto('/workbench')
  const palette = palettePanel(page)

  await palette.getByRole('button', { name: 'Processor 节点' }).click()
  await expect(palette.getByText('processor-transform', { exact: true })).toHaveCount(0)

  await page.reload()
  await expect(palettePanel(page).getByText('processor-transform', { exact: true })).toBeVisible()
})

test('active Palette search bypasses collapsed role and prefix groups', async ({ page }) => {
  await page.goto('/workbench')
  const palette = palettePanel(page)

  await palette.getByRole('button', { name: 'Processor 节点' }).click()
  await palette.getByLabel('搜索节点').fill('processor')
  await expect(palette.getByText('processor-transform', { exact: true })).toBeVisible()

  await palette.getByLabel('搜索节点').fill('')
  await palette.getByRole('button', { name: 'source', exact: true }).click()
  await expect(palette.getByText('source-alpha', { exact: true })).toHaveCount(0)

  await palette.getByLabel('搜索节点').fill('source-alpha')
  await expect(palette.getByText('source-alpha', { exact: true })).toBeVisible()
})

test('selected node highlights connected edges and dims unrelated edges without replacing runtime color', async ({ page }) => {
  await page.goto('/workbench')

  await page.locator('.react-flow__node').filter({ hasText: 'Node B' }).click()

  const edges = page.locator('.react-flow__edge')
  await expect(edges).toHaveCount(3)
  await expect(edgePath(page, 'A', 'B')).toHaveCSS('opacity', '1')
  await expect(edgePath(page, 'B', 'C')).toHaveCSS('opacity', '1')
  await expect(edgePath(page, 'D', 'E')).toHaveCSS('opacity', '0.28')
  await expect(edgePath(page, 'A', 'B')).toHaveCSS('stroke', 'rgb(22, 163, 74)')
})

test('runtime tab shows execution logs when outputs are empty', async ({ page }) => {
  await page.goto('/workbench')

  await page.locator('.react-flow__node').filter({ hasText: 'Node B' }).click()
  await page.getByRole('button', { name: 'Runtime' }).click()

  await expect(page.getByText('Output entities')).toBeVisible()
  await expect(page.getByText('Logs')).toBeVisible()
  await expect(page.getByText('/tmp/run-1-node-b-summary.json')).toBeVisible()
  await expect(page.getByText('summary', { exact: true })).toBeVisible()
})

test('shows DAG palette entries and excludes current root DAG', async ({ page }) => {
  await page.goto('/workbench')
  const palette = palettePanel(page)

  await expect(palette.getByText('common-subdag', { exact: true })).toBeVisible()
  await expect(palette.getByText('DAG 节点')).toBeVisible()
  await expect(palette.getByText('default', { exact: true })).toHaveCount(0)
})

test('quick add creates a sub-DAG instance payload', async ({ page }) => {
  await page.goto('/workbench')

  await page.getByText('Cmd/Ctrl+K').click()
  await page.getByPlaceholder('搜索节点并添加到画布中心').fill('common-subdag')
  await page.getByRole('button', { name: /common-subdag/ }).click()

  await expect.poll(() => page.evaluate(() => (window as { __lastDagPut?: { nodes?: Array<{ type?: string; dag_ref?: string }> } }).__lastDagPut?.nodes?.some((node) => node.type === 'dag' && node.dag_ref === 'common-subdag'))).toBe(true)
})

test('dragging a DAG palette entry creates a sub-DAG instance payload', async ({ page }) => {
  await page.goto('/workbench')

  await page.locator('.react-flow').evaluate((canvas) => {
    const rect = canvas.getBoundingClientRect()
    const data = new DataTransfer()
    data.setData('application/edera-dag', 'common-subdag')
    canvas.dispatchEvent(new DragEvent('dragover', {
      bubbles: true,
      cancelable: true,
      clientX: rect.left + 260,
      clientY: rect.top + 180,
      dataTransfer: data,
    }))
    canvas.dispatchEvent(new DragEvent('drop', {
      bubbles: true,
      cancelable: true,
      clientX: rect.left + 260,
      clientY: rect.top + 180,
      dataTransfer: data,
    }))
  })

  await expect.poll(() => page.evaluate(() => {
    const nodes = (window as { __lastDagPut?: { nodes?: Array<{ id?: string; type?: string; dag_ref?: string }> } }).__lastDagPut?.nodes ?? []
    return nodes.some((node) => Boolean(node.id) && node.type === 'dag' && node.dag_ref === 'common-subdag')
  })).toBe(true)
})

test('enters sub-DAG view with parent instance context and preserves root selection', async ({ page }) => {
  await page.goto('/workbench')

  await page.locator('.react-flow__node').filter({ hasText: 'Common Sub DAG' }).click({ button: 'right' })
  await page.getByRole('button', { name: '进入 Sub DAG' }).click()

  await expect(page.locator('.react-flow__node').filter({ hasText: 'Child Task' })).toBeVisible()
  await expect(page.getByText('default.sub-1 -> common-subdag')).toBeVisible()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('workbench:selectedDagName'))).toBe('default')
  await expect(page.locator('select').first()).toHaveValue('default')
})

test('sub-DAG view excludes root and current DAG from add lists', async ({ page }) => {
  await page.goto('/workbench')

  await page.locator('.react-flow__node').filter({ hasText: 'Common Sub DAG' }).click({ button: 'right' })
  await page.getByRole('button', { name: '进入 Sub DAG' }).click()

  const palette = palettePanel(page)
  await expect(palette.getByText('analysis', { exact: true })).toBeVisible()
  await expect(palette.getByText('default', { exact: true })).toHaveCount(0)
  await expect(palette.getByText('common-subdag', { exact: true })).toHaveCount(0)

  await page.getByText('Cmd/Ctrl+K').click()
  await page.getByPlaceholder('搜索节点并添加到画布中心').fill('common-subdag')
  await expect(page.getByText('没有匹配节点')).toBeVisible()
})

test('regular node context menu does not show sub-DAG enter action', async ({ page }) => {
  await page.goto('/workbench')

  await page.locator('.react-flow__node').filter({ hasText: 'Node A' }).click({ button: 'right' })

  await expect(page.getByRole('button', { name: '进入 Sub DAG' })).toHaveCount(0)
})

test('entering duplicate sub-DAG references uses the clicked parent instance', async ({ page }) => {
  let parentNodeId = ''
  await page.route(/\/api\/graph\/dag\/default$/, async (route) => {
    await route.fulfill({
      json: dag('default', [
        node('sub-a', 'dag', 'Common Sub DAG A', { dag_ref: 'common-subdag' }),
        node('sub-b', 'dag', 'Common Sub DAG B', { dag_ref: 'common-subdag' }),
      ], []),
    })
  })
  await page.route(/\/api\/child-run.*$/, async (route) => {
    const url = new URL(route.request().url())
    parentNodeId = url.searchParams.get('parent_node_id') ?? ''
    await route.fulfill({ json: { child_run_id: `${parentNodeId}-child` } })
  })
  await page.goto('/workbench')

  await page.locator('.react-flow__node').filter({ hasText: 'Common Sub DAG B' }).click({ button: 'right' })
  await page.getByRole('button', { name: '进入 Sub DAG' }).click()

  await expect(page.getByText('default.sub-b -> common-subdag')).toBeVisible()
  await expect.poll(() => parentNodeId).toBe('sub-b')
})

test('hides sub-DAG enter action when dag_ref is unresolved', async ({ page }) => {
  await page.route(/\/api\/graph\/dag\/default$/, async (route) => {
    await route.fulfill({
      json: dag('default', [
        node('stale-sub', 'dag', 'Stale Sub DAG', { dag_ref: 'missing-subdag' }),
      ], []),
    })
  })
  await page.goto('/workbench')

  await page.locator('.react-flow__node').filter({ hasText: 'Stale Sub DAG' }).click({ button: 'right' })

  await expect(page.getByRole('button', { name: '进入 Sub DAG' })).toHaveCount(0)
})

test('sub-DAG runtime uses only the clicked parent instance child run', async ({ page }) => {
  const runtimeRequests: string[] = []
  await page.route(/\/api\/graph\/dag\/default$/, async (route) => {
    await route.fulfill({
      json: dag('default', [
        node('sub-a', 'dag', 'Common Sub DAG A', { dag_ref: 'common-subdag' }),
        node('sub-b', 'dag', 'Common Sub DAG B', { dag_ref: 'common-subdag' }),
      ], []),
    })
  })
  await page.route(/\/api\/child-run.*$/, async (route) => {
    const parentNodeId = new URL(route.request().url()).searchParams.get('parent_node_id')
    await route.fulfill({ json: { child_run_id: parentNodeId === 'sub-a' ? 'child-a' : 'child-b' } })
  })
  await page.route(/\/api\/graph\/runtime-status.*$/, async (route) => {
    runtimeRequests.push(route.request().url())
    const runId = new URL(route.request().url()).searchParams.get('run_id')
    await route.fulfill({
      json: {
        node_statuses: {
          child: { status: runId === 'child-a' ? 'succeeded' : 'failed', error: null, run_id: runId },
        },
      },
    })
  })
  await page.route(/\/api\/node-outputs.*$/, async (route) => {
    const runId = new URL(route.request().url()).searchParams.get('run_id')
    await route.fulfill({
      json: {
        outputs: runId === 'child-a'
          ? [{ id: 1, type: 'child-output', attributes: { payload: { run: 'child-a' } } }]
          : [{ id: 2, type: 'child-output', attributes: { payload: { run: 'child-b' } } }],
      },
    })
  })
  await page.route(/\/api\/node-logs.*$/, async (route) => {
    const runId = new URL(route.request().url()).searchParams.get('run_id')
    await route.fulfill({
      json: {
        logs: [{
          id: runId === 'child-a' ? 1 : 2,
          run_id: runId,
          node_id: 'child',
          kind: 'summary',
          path: `/tmp/${runId}-child.json`,
          digest: `digest-${runId}`,
          size: 128,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        }],
      },
    })
  })
  await page.goto('/workbench')

  await page.locator('.react-flow__node').filter({ hasText: 'Common Sub DAG A' }).click({ button: 'right' })
  await page.getByRole('button', { name: '进入 Sub DAG' }).click()
  await page.locator('.react-flow__node').filter({ hasText: 'Child Task' }).click()
  await page.getByRole('button', { name: 'Runtime' }).click()

  await expect(page.getByText('child-a', { exact: true })).toBeVisible()
  await expect(page.getByText('/tmp/child-a-child.json')).toBeVisible()
  await expect(page.getByText('child-b', { exact: true })).toHaveCount(0)
  await expect.poll(() => runtimeRequests.some((url) => url.includes('run_id=child-a'))).toBe(true)
  await expect.poll(() => runtimeRequests.some((url) => url.includes('run_id=child-b'))).toBe(false)
})

test('sub-DAG view without child run does not fetch latest runtime fallback', async ({ page }) => {
  const runtimeRequests: string[] = []
  await page.route(/\/api\/child-run.*$/, async (route) => {
    await route.fulfill({ json: { child_run_id: null } })
  })
  await page.route(/\/api\/graph\/runtime-status.*$/, async (route) => {
    runtimeRequests.push(route.request().url())
    await route.fulfill({ json: { node_statuses: { child: { status: 'failed', error: null, run_id: 'wrong-run' } } } })
  })
  await page.goto('/workbench')

  await page.locator('.react-flow__node').filter({ hasText: 'Common Sub DAG' }).click({ button: 'right' })
  await page.getByRole('button', { name: '进入 Sub DAG' }).click()

  await expect(page.locator('.react-flow__node').filter({ hasText: 'Child Task' })).toBeVisible()
  await expect.poll(() => runtimeRequests.filter((url) => url.includes('run_id=')).length).toBe(0)
  await expect(page.locator('.react-flow__node').filter({ hasText: 'Child Task' }).locator('.animate-pulse')).toHaveCount(0)

  await page.locator('.react-flow__node').filter({ hasText: 'Child Task' }).click()
  await page.getByRole('button', { name: 'Runtime' }).click()
  await expect(page.getByText('当前 Sub DAG 实例还没有 child run')).toBeVisible()
})

test('sub-DAG view without parent run shows child-run empty state', async ({ page }) => {
  await page.route(/\/api\/dags\/default\/status$/, async (route) => {
    await route.fulfill({
      json: {
        scheduler_running: false,
        scheduler_paused: false,
        dag_name: 'default',
        current_run_id: null,
        recent_runs: [],
      },
    })
  })
  await page.goto('/workbench')

  await page.locator('.react-flow__node').filter({ hasText: 'Common Sub DAG' }).click({ button: 'right' })
  await page.getByRole('button', { name: '进入 Sub DAG' }).click()
  await page.locator('.react-flow__node').filter({ hasText: 'Child Task' }).click()
  await page.getByRole('button', { name: 'Runtime' }).click()

  await expect(page.getByText('当前 Sub DAG 实例还没有 child run')).toBeVisible()
})

test('node history expands execution logs', async ({ page }) => {
  await page.goto('/history/dag/default/nodes/B')

  await page.getByText('failed').click()

  await expect(page.getByText('Outputs')).toBeVisible()
  await expect(page.getByText('Logs')).toBeVisible()
  await expect(page.getByText('/tmp/run-1-node-b-summary.json')).toBeVisible()
  await expect(page.getByText('boom')).toBeVisible()
})

test('sub-DAG cycle error shows node ID and fix suggestion in alert', async ({ page }) => {
  const cycleErrorMessage = `无法保存 DAG 'default'：检测到 Sub DAG 循环 (Sub DAG cycle detected)

循环路径：
  default
    -> [节点 'self-ref'] -> default

问题：Sub DAG 引用形成了循环。
修复建议：请移除或修改以下任一节点的引用：
  • default 中的节点 'self-ref'`

  await page.route(/\/api\/graph\/dag\/default$/, async (route) => {
    if (route.request().method() === 'PUT') {
      await route.fulfill({
        status: 400,
        json: { error: { type: 'INVALID_ARGUMENT', message: cycleErrorMessage } },
      })
      return
    }
    await route.fulfill({
      json: dag('default', [
        node('A', 'source-alpha', 'Node A'),
        node('B', 'processor-transform', 'Node B'),
      ], [{ from: 'A', to: 'B' }]),
    })
  })

  page.on('dialog', async (dialog) => {
    expect(dialog.message()).toContain('Sub DAG cycle detected')
    expect(dialog.message()).toContain("节点 'self-ref'")
    expect(dialog.message()).toContain('修复建议')
    await dialog.accept()
  })

  await page.goto('/workbench')

  await page.evaluate(() => {
    const saveBtn = document.querySelector<HTMLButtonElement>('button[aria-label="保存"]')
      ?? Array.from(document.querySelectorAll('button')).find(b => b.textContent?.includes('保存'))
    saveBtn?.click()
  })

  await page.waitForTimeout(500)
})

function palettePanel(page: Page) {
  return page.locator('aside').filter({ hasText: '节点面板' })
}

function edgePath(page: Page, source: string, target: string) {
  return page.getByLabel(`Edge from ${source} to ${target}`).locator('path.react-flow__edge-path')
}

async function mockWorkbench(page: Page) {
  await page.route(/\/api\/graph\/dags$/, async (route) => {
    await route.fulfill({ json: { dags: ['default', 'analysis', 'common-subdag'] } })
  })
  await page.route(/\/api\/graph\/nodes$/, async (route) => {
    await route.fulfill({
      json: {
        prototypes: [
          prototype('source-alpha', 'source', 'None', 'RawItem'),
          prototype('source-beta', 'source', 'None', 'RawItem'),
          prototype('processor-transform', 'processor', 'RawItem', 'Analysis'),
          prototype('sink-write', 'sink', 'Analysis', 'None'),
        ],
      },
    })
  })
  await page.route(/\/api\/graph\/dag\/default$/, async (route) => {
    if (route.request().method() === 'PUT') {
      const payload = route.request().postDataJSON() as Record<string, unknown>
      await page.evaluate((value) => {
        ;(window as typeof window & { __lastDagPut?: Record<string, unknown> }).__lastDagPut = value
      }, payload)
      await route.fulfill({ json: { dag: { name: 'default', ...payload } } })
      return
    }
    await route.fulfill({
      json: dag('default', [
        node('A', 'source-alpha', 'Node A'),
        node('B', 'processor-transform', 'Node B'),
        node('C', 'sink-write', 'Node C'),
        node('D', 'source-beta', 'Node D'),
        node('E', 'sink-write', 'Node E'),
        node('sub-1', 'dag', 'Common Sub DAG', { dag_ref: 'common-subdag' }),
      ], [
        { from: 'A', to: 'B' },
        { from: 'B', to: 'C' },
        { from: 'D', to: 'E' },
      ]),
    })
  })
  await page.route(/\/api\/graph\/dag\/analysis$/, async (route) => {
    await route.fulfill({
      json: dag('analysis', [
        node('analysis-source', 'source-alpha', 'Market Alpha'),
        node('analysis-sink', 'sink-write', 'Report Sink'),
      ], [
        { from: 'analysis-source', to: 'analysis-sink' },
      ]),
    })
  })
  await page.route(/\/api\/graph\/dag\/common-subdag$/, async (route) => {
    await route.fulfill({
      json: dag('common-subdag', [
        node('child', 'processor-transform', 'Child Task'),
      ], []),
    })
  })
  await page.route(/\/api\/dags\/[^/]+\/status$/, async (route) => {
    const dagName = new URL(route.request().url()).pathname.split('/')[3]
    await route.fulfill({
      json: {
        scheduler_running: false,
        scheduler_paused: false,
        dag_name: dagName,
        current_run_id: null,
        recent_runs: dagName === 'default' ? [{ id: 1, run_id: 'parent-run', dag_name: 'default', source: 'manual', status: 'succeeded', started_at: '2026-01-01T00:00:00Z', ended_at: '2026-01-01T00:00:10Z', error: null }] : [],
      },
    })
  })
  await page.route(/\/api\/graph\/runtime-status$/, async (route) => {
    await route.fulfill({
      json: {
        node_statuses: {
          B: { status: 'succeeded', error: null, run_id: 'run-1' },
        },
      },
    })
  })
  await page.route(/\/api\/node-outputs.*$/, async (route) => {
    await route.fulfill({ json: { outputs: [] } })
  })
  await page.route(/\/api\/node-logs.*$/, async (route) => {
    await route.fulfill({
      json: {
        logs: [
          {
            id: 1,
            run_id: 'run-1',
            node_id: 'B',
            kind: 'summary',
            path: '/tmp/run-1-node-b-summary.json',
            digest: 'digest-summary',
            size: 128,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
      },
    })
  })
  await page.route(/\/api\/child-run.*$/, async (route) => {
    await route.fulfill({ json: { child_run_id: 'child-run-1' } })
  })
  await page.route(/\/api\/history\/dag\/default\/nodes\/B$/, async (route) => {
    await route.fulfill({
      json: {
        history: [
          {
            run: {
              id: 1,
              run_id: 'run-1',
              dag_name: 'default',
              source: 'manual',
              status: 'failed',
              started_at: '2026-01-01T00:00:00Z',
              ended_at: '2026-01-01T00:00:10Z',
              error: 'boom',
            },
            node_run: {
              id: 1,
              run_id: 'run-1',
              node_name: 'B',
              status: 'failed',
              started_at: '2026-01-01T00:00:00Z',
              ended_at: '2026-01-01T00:00:10Z',
              error: 'boom',
            },
            outputs: [],
            logs: [
              {
                id: 1,
                run_id: 'run-1',
                node_id: 'B',
                kind: 'summary',
                path: '/tmp/run-1-node-b-summary.json',
                digest: 'digest-summary',
                size: 128,
                created_at: '2026-01-01T00:00:00Z',
                updated_at: '2026-01-01T00:00:00Z',
              },
            ],
          },
        ],
      },
    })
  })
  await page.route(/\/api\/events\/node\/.*$/, async (route) => {
    await route.fulfill({ status: 204, body: '' })
  })
  await page.route(/\/api\/entities\?type=trigger$/, async (route) => {
    await route.fulfill({ json: { entities: [] } })
  })
}

function dag(name: string, nodes: ReturnType<typeof node>[], edges: Array<{ from: string; to: string }>) {
  return {
    name,
    inputs: [],
    nodes,
    edges,
    ui: {
      nodes: Object.fromEntries(nodes.map((item, index) => [item.id, { x: 80 + index * 240, y: index === 3 ? 260 : 80 }])),
    },
    entities: [],
    entity_types: {},
    entity_relations: [],
  }
}

function node(id: string, typeName: string, alias: string, extra: Record<string, unknown> = {}) {
  const isDag = typeName === 'dag'
  return {
    id,
    type: typeName,
    type_name: typeName,
    alias,
    role: isDag ? 'processor' : typeName.startsWith('source') ? 'source' : typeName.startsWith('processor') ? 'processor' : 'sink',
    input_type: isDag ? 'Any' : typeName.startsWith('source') ? 'None' : 'RawItem',
    output_type: isDag ? 'Any' : typeName.startsWith('sink') ? 'None' : typeName.startsWith('processor') ? 'Analysis' : 'RawItem',
    skills: [],
    inspector_schema: { type: 'object', properties: {} },
    config: {},
    ...extra,
  }
}

function prototype(name: string, role: 'source' | 'processor' | 'sink', inputType: string, outputType: string) {
  return {
    name,
    type: 'function',
    role,
    input_type: inputType,
    output_type: outputType,
    skills: [],
    inspector_schema: { type: 'object', properties: {} },
  }
}
