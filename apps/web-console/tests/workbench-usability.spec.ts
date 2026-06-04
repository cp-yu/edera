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

test('node history expands execution logs', async ({ page }) => {
  await page.goto('/history/dag/default/nodes/B')

  await page.getByText('failed').click()

  await expect(page.getByText('Outputs')).toBeVisible()
  await expect(page.getByText('Logs')).toBeVisible()
  await expect(page.getByText('/tmp/run-1-node-b-summary.json')).toBeVisible()
  await expect(page.getByText('boom')).toBeVisible()
})

function palettePanel(page: Page) {
  return page.locator('aside').filter({ hasText: '节点面板' })
}

function edgePath(page: Page, source: string, target: string) {
  return page.getByLabel(`Edge from ${source} to ${target}`).locator('path.react-flow__edge-path')
}

async function mockWorkbench(page: Page) {
  await page.route(/\/api\/graph\/dags$/, async (route) => {
    await route.fulfill({ json: { dags: ['default', 'analysis'] } })
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
    await route.fulfill({
      json: dag('default', [
        node('A', 'source-alpha', 'Node A'),
        node('B', 'processor-transform', 'Node B'),
        node('C', 'sink-write', 'Node C'),
        node('D', 'source-beta', 'Node D'),
        node('E', 'sink-write', 'Node E'),
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
  await page.route(/\/api\/dags\/[^/]+\/status$/, async (route) => {
    const dagName = new URL(route.request().url()).pathname.split('/')[3]
    await route.fulfill({
      json: {
        scheduler_running: false,
        scheduler_paused: false,
        dag_name: dagName,
        current_run_id: null,
        recent_runs: [],
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

function node(id: string, typeName: string, alias: string) {
  return {
    id,
    type: typeName,
    type_name: typeName,
    alias,
    role: typeName.startsWith('source') ? 'source' : typeName.startsWith('processor') ? 'processor' : 'sink',
    input_type: typeName.startsWith('source') ? 'None' : 'RawItem',
    output_type: typeName.startsWith('sink') ? 'None' : typeName.startsWith('processor') ? 'Analysis' : 'RawItem',
    skills: [],
    inspector_schema: { type: 'object', properties: {} },
    config: {},
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
