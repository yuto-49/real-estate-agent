import type { MarketContextSnapshot } from '../../utils/types'
import HazardIndicator from './HazardIndicator'
import type { HazardType } from './HazardIndicator'

interface MarketDataCardProps {
  data: MarketContextSnapshot
  compact?: boolean
}

function formatYen(value: number | null | undefined): string {
  if (value == null) return '\u2014'
  if (value >= 100_000_000) return `\u00a5${(value / 100_000_000).toFixed(1)}B`
  if (value >= 10_000) return `\u00a5${(value / 10_000).toFixed(0)}M`
  return `\u00a5${value.toLocaleString()}`
}

function formatPercent(value: number | null | undefined): string {
  if (value == null) return '\u2014'
  return `${(value * 100).toFixed(1)}%`
}

export default function MarketDataCard({ data, compact }: MarketDataCardProps) {
  const hazards: Array<{ type: HazardType; score: number }> = []
  if (data.hazard_liquefaction != null) hazards.push({ type: 'liquefaction', score: data.hazard_liquefaction })
  if (data.hazard_flood != null) hazards.push({ type: 'flood', score: data.hazard_flood })
  if (data.hazard_landslide != null) hazards.push({ type: 'landslide', score: data.hazard_landslide })

  if (compact) {
    return (
      <div className="invest-market-card" style={{ padding: 'var(--space-3)' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', alignItems: 'center' }}>
          {data.median_sale_price != null && (
            <span className="invest-market-pill at-market">
              Median {formatYen(data.median_sale_price)}
            </span>
          )}
          {hazards.map((h) => (
            <HazardIndicator key={h.type} type={h.type} score={h.score} />
          ))}
          {data.median_rent != null && (
            <span className="invest-market-pill at-market">
              Rent {formatYen(data.median_rent)}/mo
            </span>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="invest-market-card">
      <div className="invest-market-card-header">
        <span className="invest-market-card-title">Market Context</span>
        <span className="invest-market-card-source">REINFOLIB / MLIT</span>
      </div>

      {data.median_sale_price != null && (
        <div className="invest-market-row">
          <span className="invest-market-row-label">Median Sale Price</span>
          <span className="invest-market-row-value">{formatYen(data.median_sale_price)}</span>
        </div>
      )}

      {data.median_unit_price != null && (
        <div className="invest-market-row">
          <span className="invest-market-row-label">Unit Price (per m2)</span>
          <span className="invest-market-row-value">{`\u00a5${data.median_unit_price.toLocaleString()}`}</span>
        </div>
      )}

      {data.median_rent != null && (
        <div className="invest-market-row">
          <span className="invest-market-row-label">Median Rent</span>
          <span className="invest-market-row-value">{formatYen(data.median_rent)}/mo</span>
        </div>
      )}

      {data.land_price_psm != null && (
        <div className="invest-market-row">
          <span className="invest-market-row-label">Land Price (per m2)</span>
          <span className="invest-market-row-value">{`\u00a5${data.land_price_psm.toLocaleString()}`}</span>
        </div>
      )}

      {data.cap_rate != null && (
        <div className="invest-market-row">
          <span className="invest-market-row-label">Cap Rate</span>
          <span className="invest-market-row-value">{formatPercent(data.cap_rate)}</span>
        </div>
      )}

      {data.loan_rate != null && (
        <div className="invest-market-row">
          <span className="invest-market-row-label">Loan Rate</span>
          <span className="invest-market-row-value">{formatPercent(data.loan_rate)}</span>
        </div>
      )}

      {hazards.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginTop: 'var(--space-3)' }}>
          {hazards.map((h) => (
            <HazardIndicator key={h.type} type={h.type} score={h.score} />
          ))}
        </div>
      )}
    </div>
  )
}
