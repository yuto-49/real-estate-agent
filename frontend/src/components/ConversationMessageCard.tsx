import type { ConversationEvent } from '../utils/types'

const ROLE_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  system: { color: '#64748b', bg: '#f1f5f9', label: 'System' },
  buyer: { color: '#3b82f6', bg: '#eff6ff', label: 'Buyer' },
  seller: { color: '#f97316', bg: '#fff7ed', label: 'Seller' },
  broker: { color: '#22c55e', bg: '#f0fdf4', label: 'Broker' },
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  offer: 'Offer',
  counter_offer: 'Counter',
  acceptance: 'Accepted',
  rejection: 'Rejected',
  broker_intervention: 'Mediation',
  message: '',
}

interface ConversationMessageCardProps {
  event: ConversationEvent
}

function formatPrice(value: number | undefined): string {
  if (value === undefined || value === null) return '—'
  return `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

export default function ConversationMessageCard({ event }: ConversationMessageCardProps) {
  const style = ROLE_STYLES[event.role] || ROLE_STYLES.system
  const eventLabel = EVENT_TYPE_LABELS[event.event_type] || ''
  const ns = event.numerical_state
  const hasPrice = ns.buyer_offer !== undefined || ns.seller_ask !== undefined

  return (
    <div
      className="conversation-message-card"
      style={{
        borderLeft: `3px solid ${style.color}`,
        backgroundColor: style.bg,
        padding: '10px 14px',
        marginBottom: '8px',
        borderRadius: '6px',
        fontSize: '13px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        <span
          style={{
            fontWeight: 600,
            color: style.color,
            fontSize: '12px',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          {style.label}
        </span>
        {eventLabel && (
          <span
            style={{
              fontSize: '10px',
              padding: '1px 6px',
              borderRadius: '4px',
              backgroundColor: style.color,
              color: '#fff',
              fontWeight: 500,
            }}
          >
            {eventLabel}
          </span>
        )}
        <span style={{ fontSize: '11px', color: '#94a3b8', marginLeft: 'auto' }}>
          Round {event.round_number}
        </span>
      </div>

      <div style={{ color: '#334155', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
        {event.content}
      </div>

      {hasPrice && (
        <div
          style={{
            display: 'flex',
            gap: '16px',
            marginTop: '8px',
            padding: '6px 10px',
            backgroundColor: 'rgba(0,0,0,0.04)',
            borderRadius: '4px',
            fontSize: '12px',
            color: '#475569',
          }}
        >
          <span>Offer: <strong>{formatPrice(ns.buyer_offer)}</strong></span>
          <span>Ask: <strong>{formatPrice(ns.seller_ask)}</strong></span>
          <span>Spread: <strong>{formatPrice(ns.spread)}</strong></span>
        </div>
      )}
    </div>
  )
}
