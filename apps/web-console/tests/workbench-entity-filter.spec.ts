import { expect, test } from '@playwright/test'

test('groups workbench entity filter items in a compact selector', async ({ page }) => {
  await page.route(/\/api\/graph\/dag\/default$/, async (route) => {
    await route.fulfill({
      json: {
        name: 'default',
        nodes: [
          node('stock-node', 'Stock Fetcher', 'stock:600519'),
          node('source-node', 'Source Fetcher', 'source:sina'),
        ],
        edges: [],
        ui: {
          nodes: {
            'stock-node': { x: 80, y: 80 },
            'source-node': { x: 360, y: 80 },
          },
        },
        entities: [
          entity('stock:600519', 'stock', '贵州茅台'),
          entity('stock:000001', 'stock', '平安银行'),
          entity('source:sina', 'source', '新浪财经'),
          entity('sector:finance', 'sector', '金融'),
        ],
        entity_types: {},
        entity_relations: [],
      },
    })
  })
  await page.route(/\/api\/graph\/nodes$/, async (route) => {
    await route.fulfill({
      json: {
        prototypes: [
          prototype('Stock Fetcher'),
          prototype('Source Fetcher'),
        ],
      },
    })
  })
  await page.route(/\/api\/pipeline\/dag\/default\/status$/, async (route) => {
    await route.fulfill({
      json: {
        scheduler_running: false,
        scheduler_paused: false,
        dag_name: 'default',
        current_cycle_id: null,
        recent_runs: [],
      },
    })
  })

  await page.goto('/workbench')

  await expect(page.getByRole('button', { name: /实体过滤: 全部实体/ })).toBeVisible()
  await expect(page.getByTitle('贵州茅台')).toHaveCount(0)

  await page.getByRole('button', { name: /实体过滤/ }).click()
  const filterPanel = page.locator('#workbench-entity-filter-panel')
  await expect(filterPanel.getByText('stock', { exact: true })).toBeVisible()
  await expect(filterPanel.getByText('source', { exact: true })).toBeVisible()
  await expect(filterPanel.getByText('sector', { exact: true })).toBeVisible()

  await page.getByTitle('贵州茅台').click()
  await expect(page.getByRole('button', { name: /实体过滤: 贵州茅台/ })).toBeVisible()
  await expect(page.locator('.react-flow__node').filter({ hasText: 'Source Fetcher' })).toHaveCSS('opacity', '0.2')

  await page.getByTitle('新浪财经').click()
  await expect(page.getByRole('button', { name: /实体过滤: 已选 2 项/ })).toBeVisible()

  await page.getByRole('button', { name: '清除' }).click()
  await expect(page.getByRole('button', { name: /实体过滤: 全部实体/ })).toBeVisible()
  await expect(page.locator('.react-flow__node').filter({ hasText: 'Source Fetcher' })).toHaveCSS('opacity', '1')
})

function entity(ref: string, type: string, display: string) {
  return {
    id: ref,
    ref,
    type,
    display,
    attributes: {},
  }
}

function node(id: string, typeName: string, entityRef: string) {
  return {
    id,
    type: typeName,
    alias: typeName,
    config: {
      entities: [entityRef],
    },
  }
}

function prototype(name: string) {
  return {
    name,
    type: 'function',
    role: 'source',
    input_type: 'None',
    output_type: 'RawItem',
    skills: [],
    inspector_schema: { type: 'object', properties: {} },
  }
}
