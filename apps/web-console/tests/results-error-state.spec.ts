import { expect, test } from '@playwright/test'

test('C4 shows result API failures instead of empty data', async ({ page }) => {
  await page.route(/\/api\/results$/, async (route) => {
    await route.fulfill({
      status: 500,
      json: { error: { type: 'server_error', message: 'boom' } },
    })
  })

  await page.goto('/results')

  await expect(page.getByText('加载结果失败: boom')).toBeVisible()
  await expect(page.getByText('暂无数据')).toHaveCount(0)
})

test('shows explicit empty state after successful empty results', async ({ page }) => {
  await page.route(/\/api\/results$/, async (route) => {
    await route.fulfill({
      json: {
        briefing: null,
        metadata_bar: {
          cycle_id: '无',
          created_at: '',
          window: '无数据窗口',
          failed_count: 0,
          degraded: false,
          disclaimer: '本系统产出仅供学习参考，不构成投资建议。',
        },
        briefings: [],
        advices: [],
        events: [],
        event_details: {},
        summary_items: [],
        failed_sources: {},
      },
    })
  })

  await page.goto('/results')

  await expect(page.getByRole('heading', { name: '结果概览' })).toBeVisible()
  await expect(page.getByText('当前数据库没有可展示结果。')).toBeVisible()
})

test('renders returned result summary fields', async ({ page }) => {
  await page.route(/\/api\/results$/, async (route) => {
    await route.fulfill({
      json: {
        briefing: null,
        metadata_bar: {
          cycle_id: 'cycle-1',
          created_at: '2026-05-02T03:04:05+00:00',
          window: '2026-05-01 至 2026-05-02',
          failed_count: 1,
          degraded: true,
          disclaimer: '本系统产出仅供学习参考，不构成投资建议。',
        },
        briefings: [
          {
            id: 'briefing-1',
            cycle_id: 'cycle-1',
            content: 'briefing content',
            metadata: {},
            created_at: '2026-05-02T03:04:05+00:00',
          },
        ],
        advices: [],
        events: [],
        event_details: {},
        summary_items: [
          {
            id: 'advice-1',
            stock_code: '00700.HK',
            stock_name: 'Tencent',
            direction: 'buy',
            confidence: 0.8,
            reason: 'summary reason',
            evidence: [],
            source_quotes: [],
            source_urls: [],
            portfolio_snapshot: {},
            low_confidence: true,
            created_at: '2026-05-02T03:05:05+00:00',
            data_window_start: '2026-05-01T00:00:00+00:00',
            data_window_end: '2026-05-02T00:00:00+00:00',
            comparison: { verdict: 'pending' },
          },
        ],
        failed_sources: { rss: 'timeout' },
      },
    })
  })

  await page.goto('/results')

  await expect(page.getByText('cycle-1')).toBeVisible()
  await expect(page.getByText('2026-05-01 至 2026-05-02')).toBeVisible()
  await expect(page.getByText('本系统产出仅供学习参考，不构成投资建议。')).toBeVisible()
  await expect(page.getByRole('heading', { name: '历史简报' })).toBeVisible()
  await expect(page.getByText('briefing content')).toBeVisible()
  await expect(page.getByRole('heading', { name: '当前摘要' })).toBeVisible()
  await expect(page.getByText('summary reason')).toBeVisible()
  await expect(page.getByText('低置信度')).toBeVisible()
  await expect(page.getByRole('link', { name: /00700\.HK 低置信度/ }).getByText('2026-05-02')).toBeVisible()
  await expect(page.getByRole('heading', { name: '失败源' })).toBeVisible()
  await expect(page.getByText('rss')).toBeVisible()
  await expect(page.getByText('timeout')).toBeVisible()
})
