import { expect, test } from '@playwright/test'

test('source logs display status and fallback time', async ({ page }) => {
  const logRequests: string[] = []
  await page.route(/\/api\/sources\/health$/, async (route) => {
    await route.fulfill({
      json: {
        sources: [
          {
            source_name: 'rss',
            latest_status: 'failed',
            cycle_id: 'cycle-1',
            latest_run_at: null,
            success_rate: null,
            window_size: 0,
            recovery_status: 'none',
            attempt_count: 0,
            recoverable_reason: null,
            latest_failure_reason: 'timeout',
            escalated: false,
            escalation_reason: null,
            repair_task: null,
          },
        ],
      },
    })
  })
  await page.route(/\/api\/sources\/logs(?:\?.*)?$/, async (route) => {
    logRequests.push(route.request().url())
    await route.fulfill({
      json: {
        logs: [
          {
            cycle_id: 'cycle-1',
            source_name: 'rss',
            status: 'failed',
            pipeline_status: 'failed',
            started_at: null,
            ended_at: '2026-05-02T03:04:05+00:00',
            error: 'timeout',
          },
        ],
      },
    })
  })

  await page.goto('/sources')

  await expect(page.getByRole('heading', { name: '执行日志' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'failed' })).toBeVisible()
  await expect(page.getByText('2026-05-02T03:04:05')).toBeVisible()
  await expect(page.getByRole('cell', { name: 'timeout' })).toBeVisible()

  await page.getByRole('button', { name: '查看日志' }).click()
  await expect.poll(() => logRequests.some((url) => url.includes('source_name=rss'))).toBe(true)
})
