import type { ScenarioVariant } from '../utils/types'

interface Props {
  scenarios: ScenarioVariant[]
  selected: Set<string>
  onToggle: (name: string) => void
}

export default function ScenarioSelector({ scenarios, selected, onToggle }: Props) {
  return (
    <div className="scenario-selector">
      <h4>Select Scenarios</h4>
      <p style={{ color: '#888', fontSize: '0.82rem', marginBottom: '0.75rem' }}>
        Choose 1-6 market scenarios to simulate in parallel.
      </p>
      <div className="scenario-grid">
        {scenarios.map((s) => (
          <label
            key={s.name}
            className={`scenario-card ${selected.has(s.name) ? 'selected' : ''}`}
          >
            <input
              type="checkbox"
              checked={selected.has(s.name)}
              onChange={() => onToggle(s.name)}
            />
            <div className="scenario-card-body">
              <span className="scenario-card-name">{s.name.replace(/_/g, ' ')}</span>
              <span className="scenario-card-desc">{s.description}</span>
              <span className="scenario-card-rounds">Max {s.max_rounds} rounds</span>
            </div>
          </label>
        ))}
      </div>
    </div>
  )
}
