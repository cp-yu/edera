import { expect, test } from '@playwright/test'

test('handlers tab renders from list API', async ({ page }) => {
  await mockNodeApis(page)
  await page.goto('/nodes')

  await page.getByRole('button', { name: 'Handler' }).click()

  const cards = page.locator('section.rounded-xl')
  await expect(cards).toHaveCount(3)
  await expect(cards.nth(0).locator('h2')).toHaveText('reader')
  await expect(cards.nth(1).locator('h2')).toHaveText('fetcher')
  await expect(cards.nth(2).locator('h2')).toHaveText('notifier')
})

test('handlers tab shows handler code in textarea', async ({ page }) => {
  await mockNodeApis(page)
  await page.goto('/nodes')

  await page.getByRole('button', { name: 'Handler' }).click()

  const firstCard = page.locator('section.rounded-xl').first()
  const textarea = firstCard.locator('textarea')
  await expect(textarea).toHaveValue('async def run(ctx): return []\n')
})

test('handlers tab uses registry list not node handler field', async ({ page }) => {
  await page.route(/\/api\/graph\/node-types$/, async (route) => {
    await route.fulfill({
      json: {
        types: [{ name: 'reader', type: 'function', role: 'processor', handler: 'old-handler', input_type: 'Any', output_type: 'Any' }],
      },
    })
  })
  await page.route(/\/api\/graph\/skills$/, async (route) => {
    await route.fulfill({ json: { skills: [] } })
  })
  await page.route(/\/api\/graph\/handlers$/, async (route) => {
    await route.fulfill({ json: { handlers: [{ name: 'new-handler' }] } })
  })
  await page.route(/\/api\/graph\/handlers\/new-handler$/, async (route) => {
    await route.fulfill({ json: { name: 'new-handler', code: 'def run(): pass' } })
  })

  await page.goto('/nodes')
  await page.getByRole('button', { name: 'Handler' }).click()

  const cards = page.locator('section.rounded-xl')
  await expect(cards).toHaveCount(1)
  await expect(cards.first().locator('h2')).toHaveText('new-handler')
})


async function mockNodeApis(page: import('@playwright/test').Page) {
  await page.route(/\/api\/graph\/node-types$/, async (route) => {
    await route.fulfill({ json: { types: [] } })
  })
  await page.route(/\/api\/graph\/skills$/, async (route) => {
    await route.fulfill({ json: { skills: [] } })
  })
  await page.route(/\/api\/graph\/handlers$/, async (route) => {
    await route.fulfill({
      json: { handlers: [{ name: 'reader' }, { name: 'fetcher' }, { name: 'notifier' }] },
    })
  })
  for (const name of ['reader', 'fetcher', 'notifier']) {
    await page.route(`/api/graph/handlers/${name}`, async (route) => {
      await route.fulfill({ json: { name, code: 'async def run(ctx): return []\n' } })
    })
  }
}
