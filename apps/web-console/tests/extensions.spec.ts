import { expect, type Page, test } from '@playwright/test'

test('extensions route shows installed and available lists', async ({ page }) => {
  await mockExtensions(page)

  await page.goto('/extensions')

  await expect(page.getByRole('heading', { name: '扩展' })).toBeVisible()
  await expect(page.getByText('已安装')).toBeVisible()
  await expect(page.getByText('可用')).toBeVisible()
  await expect(page.getByText('rss-fetcher')).toBeVisible()
  await expect(page.getByText('web-fetcher')).toBeVisible()

  await page.getByRole('button', { name: 'web-fetcher' }).click()
  await expect(page.getByRole('heading', { name: 'web-fetcher' })).toBeVisible()
  await expect(page.getByText('web-handler')).toBeVisible()
})

test('uninstall dialog opens strategy choices', async ({ page }) => {
  await mockExtensions(page)

  await page.goto('/extensions')
  await page.getByRole('button', { name: '卸载' }).click()

  await expect(page.getByRole('heading', { name: '卸载 rss-fetcher' })).toBeVisible()
  await expect(page.getByRole('button', { name: '停用' })).toBeVisible()
  await expect(page.getByRole('button', { name: '保留修改' })).toBeVisible()
  await expect(page.getByRole('button', { name: '清除' })).toBeVisible()
})

async function mockExtensions(page: Page) {
  await page.route('**/api/extensions/*', async (route) => {
    const name = route.request().url().split('/').pop() ?? ''
    await route.fulfill({
      json: {
        manifest: {
          name,
          version: name === 'web-fetcher' ? '0.2.0' : '0.1.0',
          description: 'Demo',
          depends: [],
          handlers: [{ name: `${name === 'web-fetcher' ? 'web' : 'rss'}-handler` }],
          entity_types: [],
          imports: { entities: [] },
        },
        import_records: [],
      },
    })
  })
  await page.route('**/api/extensions/installed', async (route) => {
    await route.fulfill({
      json: {
        extensions: [
          { name: 'rss-fetcher', version: '0.1.0', enabled: true, installed_by: 'cli' },
        ],
      },
    })
  })
  await page.route('**/api/extensions/available', async (route) => {
    await route.fulfill({
      json: {
        extensions: [
          { name: 'rss-fetcher', version: '0.1.0' },
          { name: 'web-fetcher', version: '0.2.0' },
        ],
      },
    })
  })
}
