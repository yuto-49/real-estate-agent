import { expect, test } from '@playwright/test'

/**
 * Portfolio surface smoke test (Phase P6).
 *
 * Covers the top-nav wiring that ships with the investor portfolio page: the
 * Portfolio nav link is present and the mode toggle flips between the
 * individual and institutional surfaces and persists across a reload.
 */
test('portfolio nav link and mode toggle work', async ({ page }) => {
  await page.goto('/')

  // The Portfolio entry point is surfaced in the top nav.
  await expect(page.getByRole('link', { name: 'Portfolio' })).toBeVisible()

  // The mode toggle flips between the two investor surfaces.
  const toggle = page.getByTestId('portfolio-mode-toggle')
  await expect(toggle).toBeVisible()
  const initial = (await toggle.textContent())?.trim()
  await toggle.click()
  const flipped = (await toggle.textContent())?.trim()
  expect(flipped).not.toBe(initial)
  expect(['Individual', 'Institutional']).toContain(flipped)

  // The selected mode survives a reload (localStorage-backed).
  await page.reload()
  await expect(page.getByTestId('portfolio-mode-toggle')).toHaveText(flipped!)
})
