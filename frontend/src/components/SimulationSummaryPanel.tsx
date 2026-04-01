import type { SimulationReplay, PropertyVisualization } from '../utils/types'

interface SimulationSummaryPanelProps {
  replay: SimulationReplay
  currentRoundIndex: number
  propertyVisualization?: PropertyVisualization | null
}

function formatPrice(value: number | undefined | null): string {
  if (value === undefined || value === null) return '—'
  return `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

const OUTCOME_STYLES: Record<string, { color: string; bg: string }> = {
  accepted: { color: '#166534', bg: '#dcfce7' },
  rejected: { color: '#991b1b', bg: '#fee2e2' },
  max_rounds: { color: '#92400e', bg: '#fef3c7' },
  broker_stopped: { color: '#92400e', bg: '#fef3c7' },
  error: { color: '#991b1b', bg: '#fee2e2' },
}

export default function SimulationSummaryPanel({
  replay,
  currentRoundIndex,
  propertyVisualization,
}: SimulationSummaryPanelProps) {
  const { final_outcome } = replay
  const outcomeStyle = OUTCOME_STYLES[final_outcome.status] || OUTCOME_STYLES.error

  // Get numerical state at current round
  const currentEvents = replay.events.filter(e => e.round_number <= currentRoundIndex)
  const latestWithState = [...currentEvents].reverse().find(e =>
    e.numerical_state.buyer_offer !== undefined
  )
  const ns = latestWithState?.numerical_state || {}

  const priceDelta = final_outcome.status === 'accepted' && final_outcome.final_price
    ? ((final_outcome.final_price - replay.asking_price) / replay.asking_price * 100)
    : null

  // Social context tags from overlays
  const contextTags = (propertyVisualization?.overlays || [])
    .filter(o => o.overlay_type === 'sentiment_zone' || o.overlay_type === 'household_cluster')
    .map(o => o.label)

  return (
    <div
      style={{
        padding: '12px',
        borderTop: '1px solid #e2e8f0',
        backgroundColor: '#fafafa',
        fontSize: '12px',
      }}
    >
      {/* Outcome Badge */}
      <div
        style={{
          display: 'inline-block',
          padding: '3px 10px',
          borderRadius: '4px',
          backgroundColor: outcomeStyle.bg,
          color: outcomeStyle.color,
          fontWeight: 600,
          fontSize: '11px',
          textTransform: 'uppercase',
          marginBottom: '10px',
        }}
      >
        {final_outcome.status.replace('_', ' ')}
      </div>

      {/* Metrics Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '8px',
          marginBottom: '10px',
        }}
      >
        <div>
          <div style={{ color: '#94a3b8', fontSize: '10px', textTransform: 'uppercase' }}>Current Offer</div>
          <div style={{ fontWeight: 600, color: '#3b82f6' }}>{formatPrice(ns.buyer_offer)}</div>
        </div>
        <div>
          <div style={{ color: '#94a3b8', fontSize: '10px', textTransform: 'uppercase' }}>Current Ask</div>
          <div style={{ fontWeight: 600, color: '#f97316' }}>{formatPrice(ns.seller_ask)}</div>
        </div>
        <div>
          <div style={{ color: '#94a3b8', fontSize: '10px', textTransform: 'uppercase' }}>Spread</div>
          <div style={{ fontWeight: 600 }}>{formatPrice(ns.spread)}</div>
        </div>
        <div>
          <div style={{ color: '#94a3b8', fontSize: '10px', textTransform: 'uppercase' }}>Rounds</div>
          <div style={{ fontWeight: 600 }}>{final_outcome.rounds_completed} / {replay.max_rounds}</div>
        </div>
        {final_outcome.final_price && (
          <div>
            <div style={{ color: '#94a3b8', fontSize: '10px', textTransform: 'uppercase' }}>Final Price</div>
            <div style={{ fontWeight: 600, color: '#166534' }}>{formatPrice(final_outcome.final_price)}</div>
          </div>
        )}
        {priceDelta !== null && (
          <div>
            <div style={{ color: '#94a3b8', fontSize: '10px', textTransform: 'uppercase' }}>vs Asking</div>
            <div style={{ fontWeight: 600, color: priceDelta < 0 ? '#22c55e' : '#ef4444' }}>
              {priceDelta > 0 ? '+' : ''}{priceDelta.toFixed(1)}%
            </div>
          </div>
        )}
      </div>

      {/* Social Context Tags */}
      {contextTags.length > 0 && (
        <div style={{ marginTop: '8px' }}>
          <div style={{ color: '#94a3b8', fontSize: '10px', textTransform: 'uppercase', marginBottom: '4px' }}>
            Social Context
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
            {contextTags.map((tag, i) => (
              <span
                key={i}
                style={{
                  fontSize: '10px',
                  padding: '2px 6px',
                  borderRadius: '3px',
                  backgroundColor: '#e2e8f0',
                  color: '#475569',
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
