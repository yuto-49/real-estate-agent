import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import SimulationTab from './SimulationTab'
import { api } from '../../utils/api'
import type { StrategyProfile, StrategyRunRecord } from '../../utils/types'

function makeProfile(overrides: Partial<StrategyProfile> = {}): StrategyProfile {
  return {
    assumptions: {
      rent_growth: 0.04,
      expense_growth: 0.025,
      vacancy_rate: 0.05,
      hold_period_years: 10,
      exit_cap_rate: 0.07,
      loan_rate_outlook: null,
    },
    policy_config: {
      risk_tolerance: 'low',
      refi_rate_threshold: 0.06,
      sell_bias: -0.4,
      raise_rent_bias: 0.0,
      tenant_protection: true,
    },
    thesis: {
      trajectory: 'displacement_pressure',
      market_outlook: 'neutral',
      sentiment_topics: ['eviction_policy'],
      notes: 'long-term buy and hold',
    },
    ...overrides,
  }
}

function makeRecord(profile: StrategyProfile): StrategyRunRecord {
  return {
    run_id: 'run-1',
    portfolio_id: 'p1',
    status: 'completed',
    profile,
    analysis: null,
    simulation: {
      portfolio_id: 'p1',
      horizon_years: profile.assumptions.hold_period_years,
      per_holding: [
        {
          holding_id: 'h1',
          address: '123 Main St',
          horizon_years: profile.assumptions.hold_period_years,
          projected_value: 450_000,
          projected_annual_noi: 22_000,
          projected_cap_rate: 0.049,
          projected_monthly_cash_flow: 120,
          projected_recommendation: 'HOLD',
        },
      ],
      aggregate_value_projection: 450_000,
      aggregate_annual_noi_projection: 22_000,
      aggregate_cap_rate_projection: 0.049,
      notes: [],
    },
    unified: {
      portfolio_id: 'p1',
      horizon_years: profile.assumptions.hold_period_years,
      survives: true,
      confidence: 1.0,
      agreements: ['1 of 1 holdings keep the same recommendation under projection'],
      divergences: [],
      reconciliations: [
        {
          holding_id: 'h1',
          address: '123 Main St',
          today_action: 'HOLD',
          projected_action: 'HOLD',
          flipped: false,
          note: null,
        },
      ],
      summary: 'Strategy survives 10-year projection.',
    },
    error: null,
    started_at: '2026-05-15T00:00:00Z',
    completed_at: '2026-05-15T00:00:01Z',
  }
}

describe('SimulationTab', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('extracts a profile from free text and renders it', async () => {
    const profile = makeProfile()
    vi.spyOn(api.strategy, 'extract').mockResolvedValueOnce({ profile })

    render(<SimulationTab portfolioId="p1" />)

    fireEvent.change(screen.getByTestId('strategy-text'), {
      target: { value: 'long-term buy and hold, protect tenants' },
    })
    fireEvent.click(screen.getByTestId('strategy-extract-btn'))

    await waitFor(() => screen.getByTestId('strategy-profile'))
    expect(screen.getByTestId('profile-tenant-protection')).toBeChecked()
  })

  it('runs the strategy and surfaces the unified report when complete', async () => {
    const profile = makeProfile()
    const record = makeRecord(profile)
    vi.spyOn(api.strategy, 'extract').mockResolvedValueOnce({ profile })
    vi.spyOn(api.strategy, 'run').mockResolvedValueOnce({
      run_id: 'run-1',
      portfolio_id: 'p1',
      status: 'pending',
      profile,
    })
    vi.spyOn(api.strategy, 'status').mockResolvedValueOnce(record)

    render(<SimulationTab portfolioId="p1" />)

    fireEvent.change(screen.getByTestId('strategy-text'), {
      target: { value: 'long-term buy and hold' },
    })
    fireEvent.click(screen.getByTestId('strategy-extract-btn'))

    await waitFor(() => screen.getByTestId('strategy-run-btn'))
    fireEvent.click(screen.getByTestId('strategy-run-btn'))

    await waitFor(() => screen.getByTestId('strategy-result'))
    expect(screen.getByTestId('recon-h1')).toBeInTheDocument()
    // Per-holding forward projection columns (projected NOI + cash flow)
    expect(screen.getByTestId('recon-noi-h1')).toHaveTextContent('2.2万円')
    expect(screen.getByTestId('recon-cf-h1')).toHaveTextContent('¥120')
    expect(screen.getByTestId('strategy-result')).toHaveTextContent(
      '運用方針は将来試算に耐えうる見込みです',
    )
  })

  it('shows an error when extraction fails', async () => {
    vi.spyOn(api.strategy, 'extract').mockRejectedValueOnce(new Error('boom'))

    render(<SimulationTab portfolioId="p1" />)

    fireEvent.change(screen.getByTestId('strategy-text'), {
      target: { value: 'anything' },
    })
    fireEvent.click(screen.getByTestId('strategy-extract-btn'))

    await waitFor(() => screen.getByTestId('strategy-error'))
    expect(screen.getByTestId('strategy-error')).toHaveTextContent('boom')
  })
})
