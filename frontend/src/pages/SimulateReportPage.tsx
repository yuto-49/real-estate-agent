import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../utils/api'
import { formatBooleanJa, formatRecommendationLabel } from '../utils/japan'
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
            error: err instanceof Error ? err.message : 'レポートを取得できませんでした。',
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
        レポートを読み込み中…
      </div>
    )
  }
  if (state.error || !state.record) {
    return (
      <div
        className="simulate-report-page onboarding-error"
        data-testid="simulate-report-error"
      >
        {state.error ?? 'レポートを表示できません。'}
      </div>
    )
  }

  const { record } = state
  const unified = record.unified

  return (
    <div className="simulate-report-page" data-testid="simulate-report-page">
      <header className="simulate-report-page__header">
        <h2>運用レポート</h2>
        <p className="onboarding-subtle">
          実行ID {runId} ・ ステータス {record.status}
        </p>
      </header>

      {unified && (
        <section className="simulate-report-card" data-testid="report-unified-summary">
          <h3>総括</h3>
          <dl className="simulate-report-stats">
            <dt>成立性</dt>
            <dd>{formatBooleanJa(unified.survives)}</dd>
            <dt>確信度</dt>
            <dd>{(unified.confidence * 100).toFixed(0)}%</dd>
            <dt>検証期間</dt>
            <dd>{unified.horizon_years} 年</dd>
          </dl>
          <p className="simulate-report-summary">{unified.summary}</p>
        </section>
      )}

      {unified && unified.agreements.length > 0 && (
        <section className="simulate-report-card" data-testid="report-agreements">
          <h3>一致ポイント</h3>
          <ul>
            {unified.agreements.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </section>
      )}

      {unified && unified.divergences.length > 0 && (
        <section className="simulate-report-card" data-testid="report-divergences">
          <h3>差分ポイント</h3>
          <ul>
            {unified.divergences.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </section>
      )}

      {unified && unified.reconciliations.length > 0 && (
        <section className="simulate-report-card" data-testid="report-reconciliations">
          <h3>物件別の整合確認</h3>
          <table className="simulate-report-table">
            <thead>
              <tr>
                <th>所在地</th>
                <th>現在判断</th>
                <th>将来判断</th>
                <th>変化有無</th>
                <th>補足</th>
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
                  <td>{formatRecommendationLabel(rec.today_action)}</td>
                  <td>{formatRecommendationLabel(rec.projected_action)}</td>
                  <td>{formatBooleanJa(rec.flipped)}</td>
                  <td>{rec.note ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {record.status === 'failed' && (
        <p className="onboarding-error" data-testid="report-failed">
          実行に失敗しました: {record.error ?? '不明なエラー'}
        </p>
      )}

      <footer className="simulate-report-page__actions">
        <Link to="/portfolio" className="onboarding-secondary" data-testid="report-portfolio-link">
          ポートフォリオへ戻る
        </Link>
      </footer>
    </div>
  )
}
