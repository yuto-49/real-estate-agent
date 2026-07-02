interface StatCardProps {
  label: string
  value: string
  delta?: number | null
  deltaLabel?: string
  footer?: string
}

function deltaClass(delta: number): string {
  if (delta > 0) return 'positive'
  if (delta < 0) return 'negative'
  return 'neutral'
}

function formatDelta(delta: number): string {
  const sign = delta > 0 ? '+' : ''
  return `${sign}${delta.toFixed(1)}%`
}

export default function StatCard({ label, value, delta, deltaLabel, footer }: StatCardProps) {
  return (
    <div className="invest-stat-card">
      <span className="invest-stat-label">{label}</span>
      <span className="invest-stat-value">{value}</span>
      {delta != null && (
        <span className={`invest-stat-delta ${deltaClass(delta)}`}>
          {delta > 0 ? '\u2191' : delta < 0 ? '\u2193' : '\u2192'} {formatDelta(delta)}
          {deltaLabel && <span> {deltaLabel}</span>}
        </span>
      )}
      {footer && <span className="invest-stat-footer">{footer}</span>}
    </div>
  )
}
