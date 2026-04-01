interface ScenarioSwitcherProps {
  scenarios: string[]
  activeScenario: string | null
  outcomes?: Record<string, string>
  onSwitch: (scenarioName: string) => void
}

const OUTCOME_BADGES: Record<string, { color: string; label: string }> = {
  accepted: { color: '#22c55e', label: 'Deal' },
  rejected: { color: '#ef4444', label: 'No Deal' },
  max_rounds: { color: '#f59e0b', label: 'Timeout' },
  broker_stopped: { color: '#f59e0b', label: 'Stopped' },
}

function humanize(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

export default function ScenarioSwitcher({
  scenarios,
  activeScenario,
  outcomes = {},
  onSwitch,
}: ScenarioSwitcherProps) {
  if (scenarios.length <= 1) return null

  return (
    <div
      style={{
        display: 'flex',
        gap: '4px',
        overflowX: 'auto',
        padding: '6px 0',
        borderBottom: '1px solid #e2e8f0',
      }}
    >
      {scenarios.map(name => {
        const isActive = name === activeScenario
        const outcome = outcomes[name]
        const badge = outcome ? OUTCOME_BADGES[outcome] : undefined

        return (
          <button
            key={name}
            onClick={() => onSwitch(name)}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: isActive ? 600 : 400,
              color: isActive ? '#1e40af' : '#64748b',
              backgroundColor: isActive ? '#eff6ff' : 'transparent',
              border: 'none',
              borderBottom: isActive ? '2px solid #3b82f6' : '2px solid transparent',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
            }}
          >
            {humanize(name)}
            {badge && (
              <span
                style={{
                  fontSize: '9px',
                  padding: '1px 5px',
                  borderRadius: '3px',
                  backgroundColor: badge.color,
                  color: '#fff',
                  fontWeight: 500,
                }}
              >
                {badge.label}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
