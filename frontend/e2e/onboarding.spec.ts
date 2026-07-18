import { expect, test, type Page } from '@playwright/test'

/**
 * Onboarding wizard E2E (Phase P7).
 *
 * Backend-free: all `/api/*` calls are intercepted with `page.route`. The two
 * core tests (fork navigation, report rendering) need no auth. The full
 * journey seeds a fake Supabase session so the auth-gated steps (profile
 * submit, property selection, simulation launch) can run.
 */

const FAKE_USER_ID = 'e2e-user-0001'

/** Seed a non-expired Supabase session into localStorage before app boot. */
async function seedSession(page: Page): Promise<void> {
  await page.addInitScript(
    ([userId]) => {
      const oneHour = 60 * 60
      const session = {
        access_token: 'e2e-fake-access-token',
        token_type: 'bearer',
        expires_in: oneHour,
        expires_at: Math.floor(Date.now() / 1000) + oneHour,
        refresh_token: 'e2e-fake-refresh-token',
        user: {
          id: userId,
          aud: 'authenticated',
          role: 'authenticated',
          email: 'e2e@test.local',
          app_metadata: {},
          user_metadata: {},
          created_at: new Date().toISOString(),
        },
      }
      window.localStorage.setItem(
        'real-estate-agent.session',
        JSON.stringify(session),
      )
    },
    [FAKE_USER_ID],
  )
}

test.describe('onboarding wizard', () => {
  test('fork step routes to profile form and back', async ({ page }) => {
    await page.goto('/onboard')

    await expect(page.getByTestId('onboarding-fork')).toBeVisible()
    await page.getByTestId('fork-no').click()
    await expect(page.getByTestId('onboarding-profile')).toBeVisible()

    // Back returns to the fork.
    await page.getByTestId('wizard-back').click()
    await expect(page.getByTestId('onboarding-fork')).toBeVisible()
  })

  test('fork "yes" routes to the import method picker', async ({ page }) => {
    await page.goto('/onboard')
    await page.getByTestId('fork-yes').click()
    await expect(page.getByTestId('onboarding-import-picker')).toBeVisible()
    await expect(page.getByTestId('import-csv')).toBeVisible()
    await expect(page.getByTestId('import-chat')).toBeVisible()
  })

  test('report page renders a mocked unified report', async ({ page }) => {
    await page.route('**/api/strategy/run-e2e/result', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: 'run-e2e',
          portfolio_id: 'pf-1',
          status: 'completed',
          profile: {
            thesis: { market_outlook: 'bullish', trajectory: 'none', sentiment_topics: [] },
            assumptions: {
              hold_period_years: 5,
              rent_growth: 0.03,
              expense_growth: 0.02,
              exit_cap_rate: 0.07,
              loan_rate_outlook: 0.07,
              vacancy_rate: 0.05,
            },
            policy_config: {
              refi_rate_threshold: 0.075,
              tenant_protection: false,
              raise_rent_bias: 0.1,
              risk_tolerance: 'moderate',
              sell_bias: 0.1,
            },
          },
          simulation: {
            portfolio_id: 'pf-1',
            horizon_years: 5,
            per_holding: [
              {
                holding_id: 'h-1',
                address: '123 Main St 60601',
                horizon_years: 5,
                projected_value: 420000,
                projected_annual_noi: 22000,
                projected_cap_rate: 0.052,
                projected_monthly_cash_flow: 250,
                projected_recommendation: 'HOLD',
              },
            ],
            aggregate_value_projection: 420000,
            aggregate_annual_noi_projection: 22000,
            aggregate_cap_rate_projection: 0.052,
            notes: [],
          },
          unified: {
            portfolio_id: 'pf-1',
            horizon_years: 5,
            survives: true,
            confidence: 0.82,
            agreements: ['Cap rate stable'],
            divergences: [],
            reconciliations: [
              {
                holding_id: 'h-1',
                address: '123 Main St 60601',
                today_action: 'HOLD',
                projected_action: 'HOLD',
                flipped: false,
                note: null,
              },
            ],
            summary: 'Portfolio survives the simulation horizon.',
          },
          error: null,
          started_at: '2026-05-19T01:00:00Z',
          completed_at: '2026-05-19T01:00:10Z',
          steps: [],
        }),
      })
    })

    await page.goto('/simulate/run-e2e/report')

    await expect(page.getByTestId('simulate-report-page')).toBeVisible()
    await expect(page.getByTestId('report-unified-summary')).toBeVisible()
    await expect(page.getByText('Portfolio survives the simulation horizon.')).toBeVisible()
    await expect(page.getByTestId('report-portfolio-link')).toHaveAttribute(
      'href',
      '/portfolio',
    )
  })

  test('full no-portfolio journey: profile → recommend → confirm → simulate', async ({
    page,
  }) => {
    await seedSession(page)

    // --- Mock the backend surface the wizard touches. ---
    await page.route('**/api/investor-profile/', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'prof-1',
          user_id: FAKE_USER_ID,
          budget: 500000,
          strategy: 'buy_and_hold',
          target_cap_rate: 7,
          target_coc: 8,
          geography: {
            zip: '150-0001',
            prefecture: '東京都',
            municipality: '渋谷区',
            neighborhood: '神宮前',
          },
        }),
      })
    })

    await page.route('**/api/properties/recommend**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          recommendations: [
            {
              property_id: 'prop-1',
              address: '東京都渋谷区神宮前1-1-1',
              asking_price: 35000000,
              property_type: 'condo',
              bedrooms: 1,
              bathrooms: 1,
              sqft: 540,
              score: 0.81,
              rationale: ['表面利回りが目標水準に近い', '希望エリアとの整合性が高い'],
            },
          ],
          profile_id: 'prof-1',
          candidates_considered: 5,
        }),
      })
    })

    await page.route('**/api/portfolio/from-property', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'pf-synth-1',
          user_id: FAKE_USER_ID,
          name: '提案物件ポートフォリオ',
        }),
      })
    })

    await page.route('**/api/strategy/run', async (route) => {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: 'run-e2e',
          portfolio_id: 'pf-synth-1',
          status: 'pending',
          profile: {},
        }),
      })
    })

    await page.goto('/onboard')

    // Fork → profile form
    await page.getByTestId('fork-no').click()
    await expect(page.getByTestId('onboarding-profile')).toBeVisible()

    // Fill the profile.
    await page.getByTestId('profile-budget').fill('500000')
    await page.getByTestId('profile-strategy-buy_and_hold').check()
    await page.getByTestId('profile-cap-rate').fill('7')
    await page.getByTestId('profile-coc').fill('8')
    await page.getByTestId('profile-zip').fill('150-0001')
    await page.getByTestId('profile-prefecture').selectOption('東京都')
    await page.getByTestId('profile-municipality').fill('渋谷区')
    await page.getByTestId('profile-neighborhood').fill('神宮前')
    await page.getByTestId('profile-submit').click()

    // Recommendations render the mocked property.
    await expect(page.getByTestId('onboarding-recommendations')).toBeVisible()
    const selectBtn = page.getByTestId('recommendation-select-prop-1')
    await expect(selectBtn).toBeVisible()
    await selectBtn.click()

    // Confirm step → launch simulation.
    await expect(page.getByTestId('onboarding-confirm')).toBeVisible()
    const launch = page.getByTestId('confirm-launch-simulation')
    await expect(launch).toBeVisible()
    await launch.click()

    // Lands on the simulate page for the launched run.
    await expect(page).toHaveURL(/\/simulate\/run-e2e$/)
    await expect(page.getByTestId('simulate-page')).toBeVisible()
  })
})
