import { expect, test } from '@playwright/test'

/**
 * Portfolio surface smoke test (Phase P6).
 *
 * Covers the top-nav wiring that ships with the investor portfolio page after
 * the legacy investor-mode toggle was removed.
 */
test('portfolio nav link is present without the legacy mode toggle', async ({ page }) => {
  await page.goto('/')

  // The Portfolio entry point is surfaced in the top nav.
  await expect(page.getByRole('link', { name: 'ポートフォリオ' })).toBeVisible()
  await expect(page.getByTestId('portfolio-mode-toggle')).toHaveCount(0)
})
