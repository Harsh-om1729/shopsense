/**
 * End-to-end checks against the real API, database, and models.
 * Each test runs at desktop width in dark mode and at phone width in light mode.
 */
import { expect, type Page, test as base } from '@playwright/test'

// Fail any test that logs a browser error, unless it uses `base` on purpose.
const test = base.extend<{ consoleErrors: string[] }>({
  consoleErrors: [
    async ({ page }, use) => {
      const errors: string[] = []
      page.on('console', (message) => {
        if (message.type() === 'error') errors.push(message.text())
      })
      page.on('pageerror', (error) => errors.push(error.message))
      await use(errors)
      expect(errors, 'browser console errors').toEqual([])
    },
    { auto: true },
  ],
})

const PAGES = [
  { path: '/', heading: 'Overview', name: 'overview' },
  { path: '/reviews', heading: 'Review queue', name: 'reviews' },
  { path: '/sellers', heading: 'Sellers at risk', name: 'sellers' },
  { path: '/freight', heading: 'Freight estimator', name: 'freight' },
  { path: '/forecasts', heading: 'Forecasts', name: 'forecasts' },
]

// Page background colours from styles.css, as browsers report them.
const BACKGROUND = { dark: 'rgb(18, 18, 17)', light: 'rgb(246, 246, 244)' }

async function expectNoSidewaysScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow, 'page is wider than the screen').toBeLessThanOrEqual(0)
}

async function fillFreight(page: Page, customerZip: string) {
  await page.getByLabel('Customer zip prefix').fill(customerZip)
  await page.getByLabel('Seller zip prefix').fill('20040')
  for (const [label, value] of [
    ['Weight (g)', '500'],
    ['Length (cm)', '20'],
    ['Height (cm)', '10'],
    ['Width (cm)', '15'],
    ['Price', '80'],
  ]) {
    await page.getByLabel(label).fill(value)
  }
}

for (const { path, heading, name } of PAGES) {
  test(`${name} page loads with real data and fits the screen`, async ({ page }, testInfo) => {
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
    await expect(page.getByText(/historical Olist orders/)).toBeVisible()
    await expect(page.getByRole('status')).toHaveCount(0, { timeout: 15_000 })
    await expect(page.getByRole('alert')).toHaveCount(0)
    await expectNoSidewaysScroll(page)

    const scheme = testInfo.project.use.colorScheme === 'light' ? 'light' : 'dark'
    const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
    expect(background).toBe(BACKGROUND[scheme])

    await page.screenshot({
      path: testInfo.outputPath(`${testInfo.project.name}-${name}.png`),
      fullPage: true,
    })
  })
}

test('overview shows all seven problems and the held model', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.model-card')).toHaveCount(7)
  const held = page.locator('.model-card', { hasText: 'Late delivery risk' })
  await expect(held.getByText('Held')).toBeVisible()
  await expect(page.getByText('6 of 7')).toBeVisible()
  await expect(page.getByText('Loaded', { exact: true })).toBeVisible()
})

test('review queue ranks orders and changes length', async ({ page }) => {
  await page.goto('/reviews')
  await expect(page.getByText('Scored on training data.')).toBeVisible()
  await expect(page.locator('tbody tr')).toHaveCount(20)
  await page.getByLabel('Show').selectOption('50')
  await expect(page.locator('tbody tr')).toHaveCount(50)
  await expect(page.locator('tbody tr').first().locator('td').first()).toHaveText('1')
})

test('seller list shows alerts and can include every seller', async ({ page }) => {
  await page.goto('/sellers')
  const rows = page.locator('tbody tr')
  await expect(rows).toHaveCount(20)
  await expect(rows.getByText('Alert')).toHaveCount(20)
  await page.getByLabel('Alerts only').uncheck()
  await expect(page.getByText(/alerts among/)).toBeVisible()
  await expect(rows).toHaveCount(20)
})

test('freight needs product details before sending', async ({ page }) => {
  let sent = false
  page.on('request', (request) => {
    if (request.url().includes('/predict/freight')) sent = true
  })
  await page.goto('/freight')
  await page.getByRole('button', { name: 'Estimate freight' }).click()
  await expect(page.locator('form :invalid').first()).toBeVisible()
  expect(sent).toBe(false)
})

test('freight gives an estimate, and warns when the distance is unknown', async ({ page }) => {
  await page.goto('/freight')
  await fillFreight(page, '1037')
  await page.getByRole('button', { name: 'Estimate freight' }).click()
  await expect(page.locator('.result-value')).toHaveText(/^\d+\.\d{2}$/)
  await expect(page.getByText('Distance unknown.')).toHaveCount(0)

  await page.getByLabel('Customer zip prefix').fill('99999')
  await page.getByRole('button', { name: 'Estimate freight' }).click()
  await expect(page.getByText('Distance unknown.')).toBeVisible()
})

test('forecasts draw the chart and answer each question', async ({ page }) => {
  await page.goto('/forecasts')
  await expect(page.locator('.recharts-line-curve')).toBeVisible()
  await page.getByText('Show values').click()
  await expect(page.locator('details tbody tr')).toHaveCount(28)

  const category = page.locator('section', { hasText: 'Category demand' })
  await expect(category.locator('.result-value')).toContainText('items')

  const delivery = page.locator('section', { hasText: 'Delivery time' })
  await delivery.getByRole('button', { name: 'Estimate' }).click()
  await expect(delivery.locator('.result-value')).toContainText('days')
})

test('unknown addresses show a not-found page', async ({ page }) => {
  await page.goto('/no-such-page')
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
})

// These fake a broken API, so the browser logs errors on purpose. They use `base`.
// Match only API calls. A pattern like **/api/** would also catch /src/api/client.ts.
const API_CALLS = /^http:\/\/localhost:\d+\/api\//

base('a web page from another app gives a clear message, not a blank screen', async ({ page }) => {
  await page.route(API_CALLS, (route) =>
    route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>Other app</title>' }),
  )
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible()
  await expect(page.getByRole('alert').first()).toContainText('another program may be using')
})

base('a stopped API gives a clear message, not a blank screen', async ({ page }) => {
  await page.route(API_CALLS, (route) => route.abort())
  await page.goto('/reviews')
  await expect(page.getByRole('heading', { level: 1, name: 'Review queue' })).toBeVisible()
  await expect(page.getByRole('alert').first()).toContainText("Can't reach the ShopSense API")
})
