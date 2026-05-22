import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { api } from '../../utils/api'
import type { StrategyRunRecord } from '../../utils/types'

interface State {
  loading: boolean
  error: string | null
  runs: StrategyRunRecord[]
}

const INITIAL: State = { loading: true, error: null, runs: [] }

function formatStarted(ts: string): string {
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

/**
 * Compact "Most recent simulations" panel for the Overview tab.
 *
 * Pulls from ``/api/strategy/recent``. Renders the user's last few runs as
 * links into ``/simulate/:runId/report``. Silent when the user has no runs
 * yet (the wizard is the canonical way to launch one).
 */
export default function RecentSimulations() {
  const { user } = useAuth()
  const [state, setState] = useState<State>(INITIAL)

  useEffect(() => {
    if (!user?.id) {
      setState({ loading: false, error: null, runs: [] })
      return
    }
    let cancelled = false
    setState(INITIAL)
    void api.strategy
      .recent(user.id, 5)
      .then((runs) => {
        if (!cancelled) setState({ loading: false, error: null, runs })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setState({
          loading: false,
          error: err instanceof Error ? err.message : 'Could not load runs.',
          runs: [],
        })
      })
    return () => {
      cancelled = true
    }
  }, [user?.id])

  if (state.loading) {
    return <p data-testid="recent-runs-loading">Loading recent simulations…</p>
  }
  if (state.error) {
    return (
      <p className="onboarding-error" data-testid="recent-runs-error">
        {state.error}
      </p>
    )
  }
  if (state.runs.length === 0) {
    return (
      <section className="recent-runs" data-testid="recent-runs-empty">
        <h3>Most recent simulations</h3>
        <p className="onboarding-subtle">
          No runs yet. Start one from the onboarding wizard.
        </p>
        <Link to="/onboard" className="onboarding-primary" data-testid="recent-runs-onboard-cta">
          Run another simulation
        </Link>
      </section>
    )
  }

  return (
    <section className="recent-runs" data-testid="recent-runs">
      <header className="recent-runs__header">
        <h3>Most recent simulations</h3>
        <Link to="/onboard" data-testid="recent-runs-launch">
          Run another
        </Link>
      </header>
      <ul className="recent-runs__list">
        {state.runs.map((run) => (
          <li
            key={run.run_id}
            className="recent-runs__item"
            data-testid={`recent-run-${run.run_id}`}
          >
            <div className="recent-runs__row">
              <strong>{formatStarted(run.started_at)}</strong>
              <span className={`recent-runs__badge recent-runs__badge--${run.status}`}>
                {run.status}
              </span>
            </div>
            <div className="recent-runs__row">
              <span className="onboarding-subtle">
                Strategy {run.profile.thesis?.market_outlook ?? 'baseline'} ·{' '}
                {run.profile.assumptions?.hold_period_years ?? '—'}y horizon
              </span>
              <Link
                to={`/simulate/${run.run_id}/report`}
                data-testid={`recent-run-link-${run.run_id}`}
              >
                Open report
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
