import { useEffect, useState } from 'react'
import { api } from '../../utils/api'
import type { PortfolioSummaryReport } from '../../utils/types'
import StatCard from './StatCard'
import RecentSimulations from '../portfolio/RecentSimulations'

interface DashboardSectionProps {
  portfolioId: string
  userId: string
}

function formatYen(value: number): string {
  if (value >= 100_000_000) return `\u00a5${(value / 100_000_000).toFixed(1)}B`
  if (value >= 10_000) return `\u00a5${(value / 10_000).toFixed(0)}M`
  return `\u00a5${value.toLocaleString()}`
}

function formatPercent(value: number | null | undefined): string {
  if (value == null) return '\u2014'
  return `${(value * 100).toFixed(1)}%`
}

export default function DashboardSection({ portfolioId }: DashboardSectionProps) {
  const [summary, setSummary] = useState<PortfolioSummaryReport | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!portfolioId) return
    setLoading(true)
    api.portfolio
      .summary(portfolioId)
      .then(setSummary)
      .catch(() => setSummary(null))
      .finally(() => setLoading(false))
  }, [portfolioId])

  if (!portfolioId) {
    return (
      <div className="invest-section">
        <div className="invest-empty">
          <div className="invest-empty-title">ようこそ</div>
          <div className="invest-empty-text">投資家とポートフォリオを選択してください。</div>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="invest-section">
        <div className="invest-empty">ダッシュボードを読み込み中...</div>
      </div>
    )
  }

  const agg = summary?.aggregates

  return (
    <div className="invest-section" key="dashboard">
      <div className="invest-section-header">
        <h2 className="invest-section-title">ダッシュボード</h2>
        <p className="invest-section-subtitle">ポートフォリオ概要とマーケットインテリジェンス</p>
      </div>

      <div className="invest-stat-grid">
        <StatCard
          label="総資産額"
          value={agg ? formatYen(agg.total_value) : '\u2014'}
          footer={summary ? `${summary.holding_count} 物件` : undefined}
        />
        <StatCard
          label="月間キャッシュフロー"
          value={agg ? formatYen(agg.monthly_cash_flow) : '\u2014'}
          delta={agg && agg.monthly_cash_flow > 0 ? 0 : agg ? -1 : null}
        />
        <StatCard
          label="Cap Rate"
          value={agg ? formatPercent(agg.blended_cap_rate) : '\u2014'}
        />
        <StatCard
          label="DSCR"
          value={agg?.weighted_dscr != null ? agg.weighted_dscr.toFixed(2) : '\u2014'}
          footer={agg?.weighted_dscr != null && agg.weighted_dscr < 1.0 ? '基準値以下' : undefined}
        />
        <StatCard
          label="自己資本"
          value={agg ? formatYen(agg.total_equity) : '\u2014'}
        />
        <StatCard
          label="年間NOI"
          value={agg ? formatYen(agg.annual_noi) : '\u2014'}
        />
      </div>

      {summary && summary.attention.length > 0 && (
        <div className="invest-card" style={{ marginBottom: 'var(--space-6)' }}>
          <div className="invest-card-header">
            <span className="invest-card-title">注意事項</span>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
              {summary.attention.length} item{summary.attention.length !== 1 ? 's' : ''}
            </span>
          </div>
          {summary.attention.map((item) => (
            <div key={item.holding_id} className="invest-market-row">
              <span className="invest-market-row-label">{item.address}</span>
              <span className={`invest-market-pill ${item.action === 'SELL' ? 'below' : item.action === 'HOLD' ? 'at-market' : 'above'}`}>
                {item.action}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="invest-card">
        <div className="invest-card-header">
          <span className="invest-card-title">最近のシミュレーション</span>
        </div>
        <RecentSimulations />
      </div>
    </div>
  )
}
