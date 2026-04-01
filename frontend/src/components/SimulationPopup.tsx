import { useEffect, useRef, useMemo } from 'react'
import { useSimulationReplay } from '../hooks/useSimulationReplay'
import type { PropertyVisualization } from '../utils/types'
import ConversationMessageCard from './ConversationMessageCard'
import RoundTimeline from './RoundTimeline'
import ScenarioSwitcher from './ScenarioSwitcher'
import SimulationSummaryPanel from './SimulationSummaryPanel'

interface SimulationPopupProps {
  simulationId: string
  batchId?: string
  propertyVisualization?: PropertyVisualization | null
  onClose: () => void
}

const SPEED_OPTIONS = [0.5, 1, 1.5, 2]

export default function SimulationPopup({
  simulationId,
  batchId,
  propertyVisualization,
  onClose,
}: SimulationPopupProps) {
  const {
    state,
    eventsUpToCurrentRound,
    maxRound,
    loadReplay,
    loadBatchReplays,
    switchScenario,
    setRound,
    nextRound,
    prevRound,
    play,
    pause,
    reset,
    setPlaybackSpeed,
    loading,
    error,
  } = useSimulationReplay()

  const scrollRef = useRef<HTMLDivElement>(null)
  const playbackSpeed = 1

  // Load replay data on mount
  useEffect(() => {
    if (batchId) {
      loadBatchReplays(batchId)
    } else {
      loadReplay(simulationId)
    }
  }, [simulationId, batchId, loadReplay, loadBatchReplays])

  // Auto-scroll to bottom when events change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [eventsUpToCurrentRound.length])

  // Build scenario outcomes map for the switcher badges
  const scenarioOutcomes = useMemo(() => {
    if (!state.simulationReplay) return {}
    // This is a simplified version — in batch mode, each replay has its own outcome
    const outcomes: Record<string, string> = {}
    if (state.simulationReplay.scenario_name) {
      outcomes[state.simulationReplay.scenario_name] = state.simulationReplay.final_outcome.status
    }
    return outcomes
  }, [state.simulationReplay])

  const replay = state.simulationReplay

  if (loading) {
    return (
      <div className="simulation-popup" style={popupStyle}>
        <div style={headerStyle}>
          <span>Loading Simulation...</span>
          <button onClick={onClose} style={closeButtonStyle}>x</button>
        </div>
        <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
          Loading replay data...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="simulation-popup" style={popupStyle}>
        <div style={headerStyle}>
          <span>Simulation Replay</span>
          <button onClick={onClose} style={closeButtonStyle}>x</button>
        </div>
        <div style={{ padding: '20px', color: '#ef4444' }}>{error}</div>
      </div>
    )
  }

  if (!replay) return null

  const address = propertyVisualization?.address || `Property ${replay.property_id.slice(0, 8)}`

  return (
    <div className="simulation-popup" style={popupStyle}>
      {/* Header */}
      <div style={headerStyle}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: '14px', color: '#1e293b' }}>
            Simulation Replay
          </div>
          <div style={{ fontSize: '12px', color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {address}
          </div>
        </div>
        <button onClick={onClose} style={closeButtonStyle}>x</button>
      </div>

      {/* Scenario Tabs */}
      <ScenarioSwitcher
        scenarios={replay.available_scenarios}
        activeScenario={state.activeScenario}
        outcomes={scenarioOutcomes}
        onSwitch={switchScenario}
      />

      {/* Timeline */}
      <div style={{ padding: '0 12px' }}>
        <RoundTimeline
          totalRounds={maxRound}
          currentRound={state.currentRoundIndex}
          completedRounds={replay.final_outcome.rounds_completed}
          outcome={replay.final_outcome.status}
          onRoundClick={setRound}
        />
      </div>

      {/* Conversation Feed */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px',
          minHeight: 0,
        }}
      >
        {eventsUpToCurrentRound.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#94a3b8', padding: '20px' }}>
            Press Play to start the replay
          </div>
        ) : (
          eventsUpToCurrentRound.map((event, i) => (
            <ConversationMessageCard key={`${event.round_number}-${event.role}-${i}`} event={event} />
          ))
        )}
      </div>

      {/* Playback Controls */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 12px',
          borderTop: '1px solid #e2e8f0',
          backgroundColor: '#fff',
        }}
      >
        <button onClick={prevRound} style={controlBtnStyle} title="Previous round">
          {'<'}
        </button>
        {state.isReplayPlaying ? (
          <button onClick={pause} style={{ ...controlBtnStyle, backgroundColor: '#fef3c7' }} title="Pause">
            ||
          </button>
        ) : (
          <button onClick={play} style={{ ...controlBtnStyle, backgroundColor: '#dcfce7' }} title="Play">
            {'>'}
          </button>
        )}
        <button onClick={nextRound} style={controlBtnStyle} title="Next round">
          {'>'}
        </button>
        <button onClick={reset} style={controlBtnStyle} title="Reset">
          Reset
        </button>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px', alignItems: 'center' }}>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>Speed:</span>
          {SPEED_OPTIONS.map(speed => (
            <button
              key={speed}
              onClick={() => setPlaybackSpeed(speed)}
              style={{
                ...controlBtnStyle,
                fontSize: '10px',
                padding: '2px 6px',
                backgroundColor: playbackSpeed === speed ? '#3b82f6' : '#f1f5f9',
                color: playbackSpeed === speed ? '#fff' : '#475569',
              }}
            >
              {speed}x
            </button>
          ))}
        </div>
      </div>

      {/* Summary Panel */}
      <SimulationSummaryPanel
        replay={replay}
        currentRoundIndex={state.currentRoundIndex}
        propertyVisualization={propertyVisualization}
      />
    </div>
  )
}

// ── Styles ──

const popupStyle: React.CSSProperties = {
  position: 'fixed',
  top: '64px',
  right: '16px',
  bottom: '16px',
  width: '460px',
  backgroundColor: '#fff',
  borderRadius: '12px',
  boxShadow: '0 20px 60px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.05)',
  display: 'flex',
  flexDirection: 'column',
  zIndex: 1000,
  overflow: 'hidden',
}

const headerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  padding: '12px 16px',
  borderBottom: '1px solid #e2e8f0',
  backgroundColor: '#fafafa',
}

const closeButtonStyle: React.CSSProperties = {
  width: '28px',
  height: '28px',
  borderRadius: '6px',
  border: '1px solid #e2e8f0',
  backgroundColor: '#fff',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '14px',
  color: '#64748b',
  flexShrink: 0,
}

const controlBtnStyle: React.CSSProperties = {
  padding: '4px 10px',
  fontSize: '12px',
  border: '1px solid #e2e8f0',
  borderRadius: '4px',
  backgroundColor: '#f1f5f9',
  cursor: 'pointer',
  color: '#475569',
  fontWeight: 500,
}
