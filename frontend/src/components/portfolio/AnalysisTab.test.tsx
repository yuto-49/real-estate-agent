import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import AnalysisTab from './AnalysisTab'
import { api } from '../../utils/api'
import type { PortfolioSummaryReport } from '../../utils/types'

function makeReport(overrides: Partial<PortfolioSummaryReport> = {}): PortfolioSummaryReport {
  return {
    portfolio_id: 'p1',
    generated_at: '2026-05-15T00:00:00Z',
    holding_count: 1,
    aggregates: {
      total_value: 400_000,
      total_loan_balance: 240_000,
      total_equity: 160_000,
      monthly_gross_rent: 2_400,
      monthly_net_operating_income: 1_500,
      monthly_cash_flow: 100,
      annual_noi: 18_000,
      blended_cap_rate: 0.045,
      weighted_dscr: 1.05,
    },
    per_holding: [
      {
        holding_id: 'h1',
        address: '123 Main St',
        zip_code: '60615',
        asset_class: 'sfr',
        current_value: 400_000,
        monthly_cash_flow: 100,
        cap_rate: 0.045,
        dscr: 1.05,
        cash_on_cash: 0.0075,
        recommendation: 'REFI',
        recommendation_score: 0.55,
        recommendation_rationale: 'note rate above benchmark',
        market_context_available: true,
      },
    ],
    attention: [
      {
        holding_id: 'h1',
        address: '123 Main St',
        action: 'REFI',
        score: 0.55,
        rationale: 'note rate above benchmark',
      },
    ],
    market_coverage: { total: 1, with_signals: 1 },
    ...overrides,
  }
}

describe('AnalysisTab', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders aggregates, attention list, and per-holding row', async () => {
    vi.spyOn(api.portfolio, 'summary').mockResolvedValueOnce(makeReport())

    render(<AnalysisTab portfolioId="p1" />)

    await waitFor(() => screen.getByTestId('overview-tab'))

    expect(screen.getByTestId('overview-aggregates')).toBeInTheDocument()
    expect(screen.getByTestId('overview-attention')).toBeInTheDocument()
    expect(screen.getByTestId('attention-h1')).toBeInTheDocument()
    expect(screen.getByTestId('overview-row-h1')).toBeInTheDocument()
    expect(screen.getByTestId('overview-coverage')).toHaveTextContent('1 of 1')
  })

  it('hides the attention section when nothing is flagged', async () => {
    vi.spyOn(api.portfolio, 'summary').mockResolvedValueOnce(
      makeReport({
        attention: [],
        per_holding: [
          {
            holding_id: 'h1',
            address: '123 Main St',
            zip_code: '60615',
            asset_class: 'sfr',
            current_value: 400_000,
            monthly_cash_flow: 100,
            cap_rate: 0.045,
            dscr: 1.05,
            cash_on_cash: 0.0075,
            recommendation: 'HOLD',
            recommendation_score: 0.4,
            recommendation_rationale: 'steady',
            market_context_available: true,
          },
        ],
      }),
    )

    render(<AnalysisTab portfolioId="p1" />)

    await waitFor(() => screen.getByTestId('overview-tab'))

    expect(screen.queryByTestId('overview-attention')).not.toBeInTheDocument()
  })

  it('surfaces an error when the summary request fails', async () => {
    vi.spyOn(api.portfolio, 'summary').mockRejectedValueOnce(new Error('boom'))

    render(<AnalysisTab portfolioId="p1" />)

    await waitFor(() => screen.getByTestId('overview-error'))
    expect(screen.getByTestId('overview-error')).toHaveTextContent('boom')
  })
})
