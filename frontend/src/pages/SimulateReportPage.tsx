import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../utils/api'
import type { StrategyRunRecord } from '../utils/types'

interface State {
  loading: boolean
  error: string | null
  record: StrategyRunRecord | null
}

export default function SimulateReportPage() {
  const { runId } = useParams<{ runId: string }>()
  const [state, setState] = useState<State>({
    loading: true,
    error: null,
    record: null,
  })

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    setState({ loading: true, error: null, record: null })
    void api.strategy
      .result(runId)
      .then((record) => {
        if (!cancelled) setState({ loading: false, error: null, record })
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            loading: false,
            error: err instanceof Error ? err.message : 'Could not load report.',
            record: null,
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [runId])

  if (state.loading) {
    return (
      <div className="simulate-report-page" data-testid="simulate-report-loading">
        Loading report…
      </div>
    )
  }
  if (state.error || !state.record) {
    return (
      <div
        className="simulate-report-page onboarding-error"
        data-testid="simulate-report-error"
      >
        {state.error ?? 'Report unavailable.'}
      </div>
    )
  }

  const { record } = state
  const unified = record.unified

  return (
    <div className="simulate-report-page" data-testid="simulate-report-page">
      <header className="simulate-report-page__header">
        <h2>Run report</h2>
        <p className="onboarding-subtle">
          Run {runId} · Status {record.status}
        </p>
      </header>

      {unified && (
        <section className="simulate-report-card" data-testid="report-unified-summary">
          <h3>Summary</h3>
          <dl className="simulate-report-stats">
            <dt>Survives</dt>
            <dd>{unified.survives ? 'Yes' : 'No'}</dd>
            <dt>Confidence</dt>
            <dd>{(unified.confidence * 100).toFixed(0)}%</dd>
            <dt>Horizon</dt>
            <dd>{unified.horizon_years} years</dd>
          </dl>
          <p className="simulate-report-summary">{unified.summary}</p>
        </section>
      )}

      {unified && unified.agreements.length > 0 && (
        <section className="simulate-report-card" data-testid="report-agreements">
          <h3>Agreements</h3>
          <ul>
            {unified.agreements.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </section>
      )}

      {unified && unified.divergences.length > 0 && (
        <section className="simulate-report-card" data-testid="report-divergences">
          <h3>Divergences</h3>
          <ul>
            {unified.divergences.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </section>
      )}

      {unified && unified.reconciliations.length > 0 && (
        <section className="simulate-report-card" data-testid="report-reconciliations">
          <h3>Per-holding reconciliation</h3>
          <table className="simulate-report-table">
            <thead>
              <tr>
                <th>Address</th>
                <th>Today action</th>
                <th>Projected action</th>
                <th>Flipped?</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {unified.reconciliations.map((rec) => (
                <tr
                  key={rec.holding_id}
                  className={rec.flipped ? 'simulate-report-row--flipped' : ''}
                  data-testid={`report-rec-${rec.holding_id}`}
                >
                  <td>{rec.address}</td>
                  <td>{rec.today_action}</td>
                  <td>{rec.projected_action}</td>
                  <td>{rec.flipped ? 'Yes' : 'No'}</td>
                  <td>{rec.note ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {record.status === 'failed' && (
        <p className="onboarding-error" data-testid="report-failed">
          Run failed: {record.error ?? 'unknown error'}
        </p>
      )}

      <footer className="simulate-report-page__actions">
        <Link to="/portfolio" className="onboarding-secondary" data-testid="report-portfolio-link">
          Back to portfolio
        </Link>
      </footer>
    </div>
  )
}
