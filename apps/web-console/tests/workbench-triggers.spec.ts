import { expect, test } from '@playwright/test'

test('renders DAG and node trigger lists in the Inspector Triggers tab', async ({ page }) => {
  await mockWorkbench(page)

  await page.goto('/workbench')
  await page.getByRole('button', { name: 'Triggers' }).click()

  await expect(page.getByText('daily-default')).toBeVisible()
  await expect(page.getByText('cron:"0 9 * * *"', { exact: true })).toBeVisible()

  await page.locator('.react-flow__node').filter({ hasText: 'Source Fetcher' }).click()
  await page.getByRole('button', { name: 'Triggers' }).click()

  await expect(page.getByText('node-ready')).toBeVisible()
  await expect(page.locator('div').filter({ hasText: /^event:source-ready$/ })).toBeVisible()
  await expect(page.getByText('daily-default')).toHaveCount(0)
})

test('alarm_picker inserts daily cron token', async ({ page }) => {
  await mockWorkbench(page)

  await page.goto('/workbench')
  await page.getByRole('button', { name: 'Triggers' }).click()
  await page.getByLabel('触发时间').fill('09:00')
  await page.getByLabel('重复规则').selectOption('daily')
  await page.getByRole('button', { name: '插入 cron:"0 9 * * *"' }).click()

  await expect(page.locator('textarea')).toHaveValue('cron:"0 9 * * *"')
})

test('alarm_picker inserts one-time and custom weekday cron tokens', async ({ page }) => {
  await mockWorkbench(page)

  await page.goto('/workbench')
  await page.getByRole('button', { name: 'Triggers' }).click()
  await page.getByLabel('触发时间').fill('09:00')
  await page.getByLabel('重复规则').selectOption('once')
  await page.getByLabel('触发日期').fill('2026-05-30')
  await page.getByRole('button', { name: '插入 cron:"0 9 30 5 *"' }).click()

  await expect(page.locator('textarea')).toHaveValue('cron:"0 9 30 5 *"')

  await page.locator('textarea').fill('')
  await page.getByLabel('重复规则').selectOption('custom')
  await page.getByLabel('周一').uncheck()
  await page.getByLabel('周二').check()
  await page.getByLabel('周四').check()
  await page.getByRole('button', { name: '插入 cron:"0 9 * * 2,4"' }).click()

  await expect(page.locator('textarea')).toHaveValue('cron:"0 9 * * 2,4"')
})

test('event_picker enumerates Node Type emits', async ({ page }) => {
  await mockWorkbench(page)

  await page.goto('/workbench')
  await page.locator('.react-flow__node').filter({ hasText: 'Source Fetcher' }).click()
  await page.getByRole('button', { name: 'Triggers' }).click()

  await expect(page.getByLabel('事件源')).toContainText('event:source-ready')
  await page.getByLabel('事件源').selectOption('event:source-ready')
  await page.getByRole('button', { name: '插入事件' }).click()

  await expect(page.locator('textarea')).toHaveValue('event:source-ready')
  await expect(page.getByLabel('事件源')).not.toContainText('manual:dag')
  await expect(page.getByLabel('事件源')).not.toContainText('manual:node')
})

test('event_picker inserts system and custom events', async ({ page }) => {
  await mockWorkbench(page)

  await page.goto('/workbench')
  await page.getByRole('button', { name: 'Triggers' }).click()

  await expect(page.getByLabel('事件源')).toContainText('event:config-changed')
  await page.getByLabel('事件源').selectOption('event:config-changed')
  await page.getByRole('button', { name: '插入事件' }).click()
  await expect(page.locator('textarea')).toHaveValue('event:config-changed')

  await page.locator('textarea').fill('')
  await page.getByLabel('自定义事件').fill('event:custom-ready')
  await page.getByRole('button', { name: '插入事件' }).click()
  await expect(page.locator('textarea')).toHaveValue('event:custom-ready')
})

test('creates edits toggles and deletes trigger entities', async ({ page }) => {
  await mockWorkbench(page, [])

  await page.goto('/workbench')
  await page.getByRole('button', { name: 'Triggers' }).click()

  await triggerForm(page, '新建 trigger').locator('input').first().fill('market-open')
  await page.locator('textarea').fill('event:market-open')
  await page.getByRole('button', { name: '创建 trigger' }).click()

  await expect(page.getByText('market-open', { exact: true })).toBeVisible()
  await expect(page.locator('div').filter({ hasText: /^event:market-open$/ })).toBeVisible()

  await page.getByRole('button', { name: '编辑' }).click()
  await triggerForm(page, '编辑 trigger').locator('input').first().fill('market-open-edited')
  await page.locator('textarea').fill('event:market-open AND event:config-changed')
  await triggerForm(page, '编辑 trigger').getByRole('checkbox').uncheck()
  await page.getByRole('button', { name: '保存 trigger' }).click()

  await expect(page.getByText('market-open-edited')).toBeVisible()
  await expect(page.getByText('market-open', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('market-open-edited enabled')).not.toBeChecked()

  await page.getByLabel('market-open-edited enabled').click()
  await expect(page.getByLabel('market-open-edited enabled')).toBeChecked()

  await page.getByRole('button', { name: '删除' }).click()
  await expect(page.getByText('market-open-edited')).toHaveCount(0)
  await expect(page.getByText('暂无 trigger')).toBeVisible()
})

test('rejects invalid trigger expressions before save', async ({ page }) => {
  await mockWorkbench(page, [])

  await page.goto('/workbench')
  await page.getByRole('button', { name: 'Triggers' }).click()
  await page.locator('textarea').fill('manual:dag:default')
  await page.getByRole('button', { name: '创建 trigger' }).click()

  await expect(page.getByText('manual 前缀仅用于 emit，不能写入 wait_for')).toBeVisible()
})

async function mockWorkbench(
  page: import('@playwright/test').Page,
  triggers: ReturnType<typeof trigger>[] = [
    trigger('daily-default', 'cron:"0 9 * * *"', 'dag:default'),
    trigger('node-ready', 'event:source-ready', 'node:source-node'),
  ],
) {
  await page.route(/\/api\/graph\/dag\/default$/, async (route) => {
    await route.fulfill({
      json: {
        name: 'default',
        inputs: [],
        nodes: [
          node('source-node', 'Source Fetcher', [{ event: 'event:source-ready' }]),
          node('sink-node', 'Sink Writer', []),
        ],
        edges: [],
        ui: {
          nodes: {
            'source-node': { x: 80, y: 80 },
            'sink-node': { x: 360, y: 80 },
          },
        },
        entities: [],
        entity_types: {},
        entity_relations: [],
      },
    })
  })
  await page.route(/\/api\/graph\/dags$/, async (route) => {
    await route.fulfill({ json: { dags: ['default'] } })
  })
  await page.route(/\/api\/graph\/nodes$/, async (route) => {
    await route.fulfill({
      json: {
        prototypes: [
          prototype('Source Fetcher', [{ event: 'event:source-ready' }]),
          prototype('Sink Writer', []),
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
  await page.route(/\/api\/graph\/runtime-status$/, async (route) => {
    await route.fulfill({ json: { node_statuses: {} } })
  })
  await page.route(/\/api\/node-outputs.*$/, async (route) => {
    await route.fulfill({ json: { outputs: [] } })
  })
  await page.route(/\/api\/events\/node\/.*$/, async (route) => {
    await route.fulfill({ status: 204, body: '' })
  })
  await page.route(/\/api\/entities\?type=trigger$/, async (route) => {
    await route.fulfill({
      json: { entities: triggers },
    })
  })
  await page.route(/\/api\/entities$/, async (route) => {
    const request = route.request()
    if (request.method() !== 'POST') {
      await route.fallback()
      return
    }
    const body = request.postDataJSON() as { type: string; attributes: Record<string, unknown> }
    const entity = trigger(
      String(body.attributes.name),
      String(body.attributes.wait_for),
      String(body.attributes.target),
      body.attributes.enabled !== false,
    )
    triggers.push(entity)
    await route.fulfill({ json: entity })
  })
  await page.route(/\/api\/entities\/[^/?]+$/, async (route) => {
    const request = route.request()
    const id = decodeURIComponent(new URL(request.url()).pathname.split('/').pop() ?? '')
    const index = triggers.findIndex((item) => item.id === id)
    if (index < 0) {
      await route.fulfill({ status: 404, body: '' })
      return
    }
    if (request.method() === 'PUT') {
      const body = request.postDataJSON() as { attributes: Record<string, unknown> }
      triggers[index] = {
        ...triggers[index],
        attributes: { ...triggers[index].attributes, ...body.attributes },
      }
      await route.fulfill({ json: triggers[index] })
      return
    }
    if (request.method() === 'DELETE') {
      triggers.splice(index, 1)
      await route.fulfill({ json: { deleted: true } })
      return
    }
    await route.fallback()
  })
}

function node(id: string, typeName: string, emits: Array<{ event: string }>) {
  return {
    id,
    type: typeName,
    type_name: typeName,
    alias: typeName,
    role: 'source',
    input_type: 'None',
    output_type: 'RawItem',
    skills: [],
    emits,
    inspector_schema: { type: 'object', properties: {} },
    config: {},
  }
}

function prototype(name: string, emits: Array<{ event: string }>) {
  return {
    name,
    type: 'function',
    role: 'source',
    input_type: 'None',
    output_type: 'RawItem',
    skills: [],
    emits,
    inspector_schema: { type: 'object', properties: {} },
  }
}

function triggerForm(page: import('@playwright/test').Page, title: string) {
  return page.getByText(title, { exact: true }).locator('xpath=..')
}

function trigger(name: string, waitFor: string, target: string, enabled = true) {
  return {
    id: name,
    ref: `trigger:${name}`,
    type: 'trigger',
    display: name,
    attributes: {
      name,
      wait_for: waitFor,
      target,
      enabled,
    },
  }
}
