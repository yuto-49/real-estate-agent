interface RoundTimelineProps {
  totalRounds: number
  currentRound: number
  completedRounds: number
  outcome: string
  onRoundClick: (round: number) => void
}

const OUTCOME_COLORS: Record<string, string> = {
  accepted: '#22c55e',
  rejected: '#ef4444',
  max_rounds: '#f59e0b',
  broker_stopped: '#f59e0b',
  error: '#ef4444',
}

export default function RoundTimeline({
  totalRounds,
  currentRound,
  completedRounds,
  outcome,
  onRoundClick,
}: RoundTimelineProps) {
  const rounds = Array.from({ length: totalRounds + 1 }, (_, i) => i)

  return (
    <div style={{ padding: '8px 0' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '2px',
          overflowX: 'auto',
          padding: '4px 0',
        }}
      >
        {rounds.map(round => {
          const isActive = round === currentRound
          const isCompleted = round <= completedRounds
          const isFinal = round === completedRounds
          const outcomeColor = isFinal ? OUTCOME_COLORS[outcome] : undefined

          return (
            <button
              key={round}
              onClick={() => isCompleted ? onRoundClick(round) : undefined}
              disabled={!isCompleted}
              title={`Round ${round}${isFinal ? ` — ${outcome}` : ''}`}
              style={{
                width: isActive ? '28px' : '20px',
                height: isActive ? '28px' : '20px',
                borderRadius: '50%',
                border: isActive ? '2px solid #3b82f6' : '1px solid #e2e8f0',
                backgroundColor: isActive
                  ? '#3b82f6'
                  : outcomeColor
                    ? outcomeColor
                    : isCompleted
                      ? '#cbd5e1'
                      : '#f8fafc',
                color: isActive || outcomeColor ? '#fff' : isCompleted ? '#475569' : '#cbd5e1',
                fontSize: '10px',
                fontWeight: isActive ? 700 : 500,
                cursor: isCompleted ? 'pointer' : 'default',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                transition: 'all 0.15s ease',
                padding: 0,
              }}
            >
              {round}
            </button>
          )
        })}
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '11px',
          color: '#94a3b8',
          marginTop: '4px',
          padding: '0 2px',
        }}
      >
        <span>Start</span>
        <span>Round {currentRound} / {completedRounds}</span>
        <span>
          {outcome && (
            <span style={{ color: OUTCOME_COLORS[outcome] || '#94a3b8', fontWeight: 600 }}>
              {outcome.replace('_', ' ')}
            </span>
          )}
        </span>
      </div>
    </div>
  )
}
