import { act, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import SimulatePage from './SimulatePage'
import { api } from '../utils/api'
import type { StrategyRunRecord } from '../utils/types'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []

  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null
  close = vi.fn()

  constructor(_url: string) {
    FakeWebSocket.instances.push(this)
  }
}

function makeRecord(overrides: Partial<StrategyRunRecord> = {}): StrategyRunRecord {
  return {
    run_id: 'run-1',
    portfolio_id: 'portfolio-1',
    status: 'completed',
    profile: {
      thesis: {
        market_outlook: 'bullish',
        trajectory: 'neighborhood_trajectory',
        sentiment_topics: [],
      },
      assumptions: {
        hold_period_years: 7,
        rent_growth: 0.015,
        expense_growth: 0.01,
        exit_cap_rate: 0.045,
        loan_rate_outlook: 0.018,
        vacancy_rate: 0.04,
      },
      policy_config: {
        refi_rate_threshold: 0.02,
        tenant_protection: true,
        raise_rent_bias: 0.05,
        risk_tolerance: 'moderate',
        sell_bias: 0,
      },
    },
    analysis: null,
    simulation: null,
    unified: null,
    error: null,
    started_at: '2026-07-17T00:00:00Z',
    completed_at: '2026-07-17T00:00:04Z',
    steps: [
      {
        type: 'step.analysis_built',
        label: '分析を作成しました',
        detail: '1件の保有物件を確認',
        at: '2026-07-17T00:00:01Z',
      },
      {
        type: 'run.completed',
        label: '将来シミュレーションを完了しました',
        detail: null,
        at: '2026-07-17T00:00:04Z',
      },
    ],
    ...overrides,
  }
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/simulate/:runId" element={<SimulatePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('SimulatePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
  })

  it('falls back to polling when websocket streaming is unavailable', async () => {
    vi.spyOn(api.strategy, 'status').mockResolvedValue(makeRecord())

    renderAt('/simulate/run-1')

    await waitFor(() => {
      expect(FakeWebSocket.instances).toHaveLength(1)
    })

    act(() => {
      FakeWebSocket.instances[0].onerror?.()
    })

    await waitFor(() => {
      expect(api.strategy.status).toHaveBeenCalledWith('run-1')
    })
    await waitFor(() => {
      expect(screen.getByTestId('simulate-view-report')).toBeInTheDocument()
    })

    expect(screen.getByText('分析を作成しました')).toBeInTheDocument()
    expect(screen.getByText(/1件の保有物件を確認/)).toBeInTheDocument()
    expect(screen.getByText('将来シミュレーションを完了しました')).toBeInTheDocument()
  })
})
