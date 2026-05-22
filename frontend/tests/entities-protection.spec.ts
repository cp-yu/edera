import { expect, type Page, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'

const yamlByType: Record<string, string> = {
  node: `display_name: Node
business_id_field: name
display_template: "{name}"
storage_tier: filesystem
system_protected: true
schema:
  type: object
`,
  relation: `display_name: Relation
business_id_field: id
display_template: "{id}"
schema:
  type: object
`,
  stock: `display_name: Stock
business_id_field: code
display_template: "{code}"
schema:
  type: object
`,
}

test('C5 protects system and relation entity type cards with readonly view', async ({ page }) => {
  mkdirSync('test-results/c5-entity-type-protection', { recursive: true })

  await page.route(/\/api\/config\/entity-types$/, async (route) => {
    await route.fulfill({
      json: {
        types: {
          node: entityType('Node', 'name', true),
          relation: entityType('Relation', 'id', false),
          stock: entityType('Stock', 'code', false),
        },
      },
    })
  })
  await page.route(/\/api\/config\/entity-types\/[^/]+$/, async (route) => {
    const name = route.request().url().split('/').pop() ?? ''
    await route.fulfill({ json: { name, content: yamlByType[name] ?? '' } })
  })
  await page.route(/\/api\/entities$/, async (route) => {
    await route.fulfill({ json: { entities: [] } })
  })
  await page.route(/\/api\/entity-relations$/, async (route) => {
    await route.fulfill({ json: { relations: [] } })
  })
  await page.route(/\/api\/entity-relations\/types$/, async (route) => {
    await route.fulfill({ json: { types: [] } })
  })

  await page.goto('/entities')

  const nodeCard = cardByType(page, 'node')
  const relationCard = cardByType(page, 'relation')
  const stockCard = cardByType(page, 'stock')

  await expect(nodeCard.getByRole('button', { name: '查看' })).toBeVisible()
  await expect(nodeCard.getByRole('button', { name: '编辑' })).toHaveCount(0)
  await expect(nodeCard.getByRole('button', { name: '删除' })).toHaveCount(0)

  await expect(relationCard.getByRole('button', { name: '查看' })).toBeVisible()
  await expect(relationCard.getByRole('button', { name: '编辑' })).toHaveCount(0)
  await expect(relationCard.getByRole('button', { name: '删除' })).toHaveCount(0)

  await expect(stockCard.getByRole('button', { name: '编辑' })).toBeVisible()
  await expect(stockCard.getByRole('button', { name: '删除' })).toBeVisible()
  await expect(stockCard.getByRole('button', { name: '查看' })).toHaveCount(0)

  await page.screenshot({ path: 'test-results/c5-entity-type-protection/cards.png', fullPage: true })

  await nodeCard.getByRole('button', { name: '查看' }).click()
  await expect(page.getByRole('heading', { name: '查看 node' })).toBeVisible()
  await expect(page.locator('textarea')).toHaveJSProperty('readOnly', true)
  await expect(page.getByRole('button', { name: '保存' })).toHaveCount(0)
  await page.screenshot({ path: 'test-results/c5-entity-type-protection/readonly-dialog.png', fullPage: true })
})

function entityType(displayName: string, businessIdField: string, systemProtected: boolean) {
  return {
    display_name: displayName,
    business_id_field: businessIdField,
    display_template: `{${businessIdField}}`,
    system_protected: systemProtected,
    schema: { type: 'object', properties: {} },
    field_permissions: {},
    validate: true,
  }
}

function cardByType(page: Page, typeName: string) {
  return page.locator('article').filter({ has: page.locator('p', { hasText: typeName }) })
}
