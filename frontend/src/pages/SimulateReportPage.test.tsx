import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

import SimulateReportPage from './SimulateReportPage'
import { api } from '../utils/api'
import type { StrategyRunRecord } from '../utils/types'

function fakeRecord(over: Partial<StrategyRunRecord> = {}): StrategyRunRecord {
  return {
    run_id: 'run-1',
    portfolio_id: 'p-1',
    status: 'completed',
    profile: {
      thesis: {
        market_outlook: 'bullish',
        trajectory: 'gentrifying',
        sentiment_topics: [],
      },
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
    analysis: null,
    simulation: {
      portfolio_id: 'p-1',
      horizon_years: 5,
      per_holding: [
        {
          holding_id: 'h-1',
          address: '123 Main',
          horizon_years: 5,
          projected_value: 420_000,
          projected_annual_noi: 22_000,
          projected_cap_rate: 0.052,
          projected_monthly_cash_flow: 250,
          projected_recommendation: 'HOLD',
        },
      ],
      aggregate_value_projection: 420_000,
      aggregate_annual_noi_projection: 22_000,
      aggregate_cap_rate_projection: 0.052,
      notes: [],
    },
    unified: {
      portfolio_id: 'p-1',
      horizon_years: 5,
      survives: true,
      confidence: 0.82,
      agreements: ['Cap rate stable', 'DSCR healthy'],
      divergences: [],
      reconciliations: [
        {
          holding_id: 'h-1',
          address: '123 Main',
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
    ...over,
  }
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/simulate/:runId/report" element={<SimulateReportPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('SimulateReportPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders unified summary + agreements + reconciliation table', async () => {
    vi.spyOn(api.strategy, 'result').mockResolvedValue(fakeRecord())

    renderAt('/simulate/run-1/report')

    await waitFor(() => {
      expect(screen.getByTestId('simulate-report-page')).toBeInTheDocument()
    })
    expect(screen.getByTestId('report-unified-summary')).toBeInTheDocument()
    expect(screen.getByTestId('report-agreements')).toBeInTheDocument()
    expect(screen.queryByTestId('report-divergences')).not.toBeInTheDocument()
    expect(screen.getByTestId('report-reconciliations')).toBeInTheDocument()
    expect(screen.getByText(/Portfolio survives/)).toBeInTheDocument()
    expect(screen.getByText('82%')).toBeInTheDocument()
  })

  it('renders failed state', async () => {
    vi.spyOn(api.strategy, 'result').mockResolvedValue(
      fakeRecord({ status: 'failed', error: 'portfolio_not_found', unified: null }),
    )
    renderAt('/simulate/run-1/report')
    await waitFor(() => {
      expect(screen.getByTestId('report-failed')).toBeInTheDocument()
    })
    expect(screen.getByText(/portfolio_not_found/)).toBeInTheDocument()
  })

  it('renders error state when the fetch fails', async () => {
    vi.spyOn(api.strategy, 'result').mockRejectedValue(new Error('boom'))
    renderAt('/simulate/run-1/report')
    await waitFor(() => {
      expect(screen.getByTestId('simulate-report-error')).toBeInTheDocument()
    })
    expect(screen.getByText(/boom/)).toBeInTheDocument()
  })
})
