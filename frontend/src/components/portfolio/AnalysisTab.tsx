import { useEffect, useState } from 'react'
import { api } from '../../utils/api'
import { formatJpyCompact, formatRecommendationLabel } from '../../utils/japan'
import type { PortfolioSummaryReport } from '../../utils/types'

interface AnalysisTabProps {
  portfolioId: string
}

const ACTION_BLURB: Record<string, string> = {
  HOLD: '現状維持で問題ありません。',
  RAISE_RENT: '市場賃料に合わせた賃料改定余地があります。',
  REFI: '借入条件の見直しで収支改善が見込めます。',
  SELL: '市況上、売却の検討余地があります。',
  IMPROVE: '改修や改善投資で競争力を高められます。',
}

function formatPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

function formatRatio(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—'
  return value.toFixed(digits)
}

export default function AnalysisTab({ portfolioId }: AnalysisTabProps) {
  const [report, setReport] = useState<PortfolioSummaryReport | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    setReport(null)
    api.portfolio
      .summary(portfolioId)
      .then((r) => {
        if (active) setReport(r)
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : '概要レポートを取得できませんでした。')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [portfolioId])

  if (loading) {
    return (
      <p className="portfolio-empty" data-testid="overview-loading">
        ポートフォリオ概要を読み込み中…
      </p>
    )
  }

  if (error) {
    return (
      <p className="portfolio-error" data-testid="overview-error">
        {error}
      </p>
    )
  }

  if (!report) return null

  const agg = report.aggregates

  return (
    <div className="overview-tab" data-testid="overview-tab">
      <section className="overview-aggregate-strip" data-testid="overview-aggregates">
        <Metric label="保有件数" value={String(report.holding_count)} />
        <Metric label="資産総額" value={formatJpyCompact(agg.total_value)} />
        <Metric label="純資産" value={formatJpyCompact(agg.total_equity)} />
        <Metric label="月次CF" value={formatJpyCompact(agg.monthly_cash_flow)} />
        <Metric label="加重平均利回り" value={formatPercent(agg.blended_cap_rate)} />
        <Metric label="加重平均DSCR" value={formatRatio(agg.weighted_dscr)} />
      </section>

      {report.attention.length > 0 && (
        <section className="overview-attention" data-testid="overview-attention">
          <h3>優先して確認したい項目</h3>
          <ul>
            {report.attention.map((item) => (
              <li key={item.holding_id} data-testid={`attention-${item.holding_id}`}>
                <span className={`overview-action overview-action-${item.action.toLowerCase()}`}>
                  {formatRecommendationLabel(item.action)}
                </span>
                <span className="overview-attention-address">{item.address}</span>
                <span className="overview-attention-rationale">{item.rationale}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="overview-per-holding" data-testid="overview-per-holding">
        <h3>物件別分析</h3>
        {report.per_holding.length === 0 ? (
          <p className="portfolio-empty">保有物件がありません。保有物件タブから追加してください。</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>所在地</th>
                <th>評価額</th>
                <th>利回り</th>
                <th>DSCR</th>
                <th>自己資金利回り</th>
                <th>月次CF</th>
                <th>推奨</th>
              </tr>
            </thead>
            <tbody>
              {report.per_holding.map((row) => (
                <tr key={row.holding_id} data-testid={`overview-row-${row.holding_id}`}>
                  <td>{row.address}</td>
                  <td>{formatJpyCompact(row.current_value)}</td>
                  <td>{formatPercent(row.cap_rate)}</td>
                  <td>{formatRatio(row.dscr)}</td>
                  <td>{formatPercent(row.cash_on_cash)}</td>
                  <td>{formatJpyCompact(row.monthly_cash_flow)}</td>
                  <td>
                    <span
                      className={`overview-action overview-action-${row.recommendation.toLowerCase()}`}
                      title={ACTION_BLURB[row.recommendation] ?? row.recommendation_rationale}
                    >
                      {formatRecommendationLabel(row.recommendation)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <p className="overview-coverage" data-testid="overview-coverage">
        市場シグナル取得済み: {report.market_coverage.total} 件中 {report.market_coverage.with_signals} 件
      </p>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="overview-metric">
      <span className="overview-metric-label">{label}</span>
      <span className="overview-metric-value">{value}</span>
    </div>
  )
}
