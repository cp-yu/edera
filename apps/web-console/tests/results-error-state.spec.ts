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
