import type { BatchSimulationStatus } from '../utils/types'

interface Props {
  batchStatus: BatchSimulationStatus
}

export default function SimulationRunner({ batchStatus }: Props) {
  const scenarios = batchStatus.scenarios ?? []
  const completed_scenarios = batchStatus.completed_scenarios ?? 0
  const total_scenarios = batchStatus.total_scenarios ?? 0
  const total_progress = batchStatus.total_progress ?? 0

  return (
    <div className="sim-runner">
      <div className="sim-progress">
        <div className="sim-progress-header">
          <span>{completed_scenarios} of {total_scenarios} scenarios complete</span>
          <span>{total_progress}%</span>
        </div>
        <div className="workflow-progress-bar">
          <div
            className={`workflow-progress-fill ${completed_scenarios === total_scenarios ? 'complete' : ''}`}
            style={{ width: `${total_progress}%` }}
          />
        </div>
      </div>

      <div className="sim-runner-scenarios">
        {scenarios.map((s) => (
          <div key={s.scenario} className="sim-runner-scenario">
            <div className="sim-runner-scenario-header">
              <span className="sim-runner-scenario-name">{s.scenario.replace(/_/g, ' ')}</span>
              <span className={`status-pill ${s.status === 'completed' ? 'ok' : s.status === 'failed' ? 'error' : 'running'}`}>
                {s.status}
              </span>
            </div>
            <div className="workflow-progress-bar" style={{ height: '8px' }}>
              <div
                className={`workflow-progress-fill ${s.status === 'completed' ? 'complete' : s.status === 'failed' ? 'failed' : ''}`}
                style={{ width: `${s.progress}%` }}
              />
            </div>
            <span style={{ fontSize: '0.75rem', color: '#888' }}>
              Round {s.current_round} / {s.max_rounds}
            </span>
          </div>
        ))}
      </div>

      {batchStatus.status !== 'completed' && (
        <div className="sim-thinking">
          <span className="workflow-spinner" /> Agents negotiating across scenarios...
        </div>
      )}
    </div>
  )
}
