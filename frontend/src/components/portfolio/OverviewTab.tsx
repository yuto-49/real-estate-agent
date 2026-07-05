import { useEffect, useState } from 'react'
import { api } from '../../utils/api'
import type { PortfolioSummaryReport } from '../../utils/types'

interface OverviewTabProps {
  portfolioId: string
}

const ACTION_BLURB: Record<string, string> = {
  HOLD: 'Stay the course — no action recommended.',
  RAISE_RENT: 'Rent has room to move toward market.',
  REFI: 'Refinance — the note rate is materially above the benchmark.',
  SELL: 'Market conditions favor listing this holding.',
  IMPROVE: 'Invest in the property to protect tenant retention.',
}

function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'JPY',
    maximumFractionDigits: 0,
  })
}

function formatPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

function formatRatio(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—'
  return value.toFixed(digits)
}

export default function OverviewTab({ portfolioId }: OverviewTabProps) {
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
        if (active) setError(err instanceof Error ? err.message : 'Failed to load summary')
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
        Loading portfolio summary…
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
        <Metric label="物件数" value={String(report.holding_count)} />
        <Metric label="総資産額" value={formatMoney(agg.total_value)} />
        <Metric label="自己資本" value={formatMoney(agg.total_equity)} />
        <Metric label="月間キャッシュフロー" value={formatMoney(agg.monthly_cash_flow)} />
        <Metric label="加重キャップレート" value={formatPercent(agg.blended_cap_rate)} />
        <Metric label="加重DSCR" value={formatRatio(agg.weighted_dscr)} />
      </section>

      {report.attention.length > 0 && (
        <section className="overview-attention" data-testid="overview-attention">
          <h3>注意が必要な物件</h3>
          <ul>
            {report.attention.map((item) => (
              <li key={item.holding_id} data-testid={`attention-${item.holding_id}`}>
                <span className={`overview-action overview-action-${item.action.toLowerCase()}`}>
                  {item.action}
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
          <p className="portfolio-empty">物件がまだありません — 保有物件タブから追加してください。</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>住所</th>
                <th>評価額</th>
                <th>キャップレート</th>
                <th>DSCR</th>
                <th>CoC</th>
                <th>月間CF</th>
                <th>推奨アクション</th>
              </tr>
            </thead>
            <tbody>
              {report.per_holding.map((row) => (
                <tr key={row.holding_id} data-testid={`overview-row-${row.holding_id}`}>
                  <td>{row.address}</td>
                  <td>{formatMoney(row.current_value)}</td>
                  <td>{formatPercent(row.cap_rate)}</td>
                  <td>{formatRatio(row.dscr)}</td>
                  <td>{formatPercent(row.cash_on_cash)}</td>
                  <td>{formatMoney(row.monthly_cash_flow)}</td>
                  <td>
                    <span
                      className={`overview-action overview-action-${row.recommendation.toLowerCase()}`}
                      title={ACTION_BLURB[row.recommendation] ?? row.recommendation_rationale}
                    >
                      {row.recommendation}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <p className="overview-coverage" data-testid="overview-coverage">
        Market signals available for {report.market_coverage.with_signals} of{' '}
        {report.market_coverage.total} holdings.
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
