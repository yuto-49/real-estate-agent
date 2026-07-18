import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { api } from '../../utils/api'
import { formatJaDateTime, formatMarketOutlookLabel } from '../../utils/japan'
import type { StrategyRunRecord } from '../../utils/types'

interface State {
  loading: boolean
  error: string | null
  runs: StrategyRunRecord[]
}

const INITIAL: State = { loading: true, error: null, runs: [] }

function formatStarted(ts: string): string {
  return formatJaDateTime(ts)
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
          error: err instanceof Error ? err.message : '実行履歴を取得できませんでした。',
          runs: [],
        })
      })
    return () => {
      cancelled = true
    }
  }, [user?.id])

  if (state.loading) {
    return <p data-testid="recent-runs-loading">直近の試算を読み込み中…</p>
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
        <h3>直近のシミュレーション</h3>
        <p className="onboarding-subtle">
          まだ試算結果がありません。オンボーディングから新しい試算を開始してください。
        </p>
        <Link to="/onboard" className="onboarding-primary" data-testid="recent-runs-onboard-cta">
          新しい試算を始める
        </Link>
      </section>
    )
  }

  return (
    <section className="recent-runs" data-testid="recent-runs">
      <header className="recent-runs__header">
        <h3>直近のシミュレーション</h3>
        <Link to="/onboard" data-testid="recent-runs-launch">
          新規作成
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
                見通し {formatMarketOutlookLabel(run.profile.thesis?.market_outlook)} ・
                保有期間 {run.profile.assumptions?.hold_period_years ?? '—'} 年
              </span>
              <Link
                to={`/simulate/${run.run_id}/report`}
                data-testid={`recent-run-link-${run.run_id}`}
              >
                レポートを見る
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
