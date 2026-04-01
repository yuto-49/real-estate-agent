import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { api } from '../utils/api'
import type { SimulationReplay, ConversationEvent, SimulationUIState } from '../utils/types'

const DEFAULT_PLAYBACK_INTERVAL_MS = 1500

interface UseSimulationReplayReturn {
  state: SimulationUIState
  eventsUpToCurrentRound: ConversationEvent[]
  currentRoundEvents: ConversationEvent[]
  maxRound: number
  loadReplay: (simulationId: string) => Promise<void>
  loadBatchReplays: (batchId: string) => Promise<void>
  switchScenario: (scenarioName: string) => void
  setRound: (index: number) => void
  nextRound: () => void
  prevRound: () => void
  play: () => void
  pause: () => void
  reset: () => void
  setPlaybackSpeed: (speed: number) => void
  openPopup: () => void
  closePopup: () => void
  loading: boolean
  error: string | null
}

export function useSimulationReplay(): UseSimulationReplayReturn {
  const [state, setState] = useState<SimulationUIState>({
    selectedPropertyId: null,
    activeSimulationId: null,
    activeScenario: null,
    currentRoundIndex: 0,
    isPopupOpen: false,
    isReplayPlaying: false,
    mapCenter: null,
    propertyVisualization: null,
    simulationReplay: null,
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [playbackSpeed, setPlaybackSpeedState] = useState(1)
  const [batchReplays, setBatchReplays] = useState<SimulationReplay[]>([])

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Derive max round from events
  const maxRound = useMemo(() => {
    if (!state.simulationReplay) return 0
    const rounds = state.simulationReplay.events.map(e => e.round_number)
    return rounds.length > 0 ? Math.max(...rounds) : 0
  }, [state.simulationReplay])

  // Events filtered up to current round
  const eventsUpToCurrentRound = useMemo(() => {
    if (!state.simulationReplay) return []
    return state.simulationReplay.events.filter(
      e => e.round_number <= state.currentRoundIndex
    )
  }, [state.simulationReplay, state.currentRoundIndex])

  // Events for exactly the current round
  const currentRoundEvents = useMemo(() => {
    if (!state.simulationReplay) return []
    return state.simulationReplay.events.filter(
      e => e.round_number === state.currentRoundIndex
    )
  }, [state.simulationReplay, state.currentRoundIndex])

  // Clean up interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  const stopPlayback = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setState(prev => ({ ...prev, isReplayPlaying: false }))
  }, [])

  const loadReplay = useCallback(async (simulationId: string) => {
    setLoading(true)
    setError(null)
    stopPlayback()
    try {
      const replay = await api.visualization.getReplay(simulationId)
      setState(prev => ({
        ...prev,
        activeSimulationId: simulationId,
        activeScenario: replay.scenario_name,
        currentRoundIndex: 0,
        simulationReplay: replay,
        selectedPropertyId: replay.property_id,
        isPopupOpen: true,
      }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load replay')
    } finally {
      setLoading(false)
    }
  }, [stopPlayback])

  const loadBatchReplays = useCallback(async (batchId: string) => {
    setLoading(true)
    setError(null)
    stopPlayback()
    try {
      const result = await api.visualization.getBatchReplays(batchId)
      setBatchReplays(result.replays)
      if (result.replays.length > 0) {
        const first = result.replays[0]
        setState(prev => ({
          ...prev,
          activeSimulationId: first.simulation_id,
          activeScenario: first.scenario_name,
          currentRoundIndex: 0,
          simulationReplay: first,
          selectedPropertyId: first.property_id,
          isPopupOpen: true,
        }))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load batch replays')
    } finally {
      setLoading(false)
    }
  }, [stopPlayback])

  const switchScenario = useCallback((scenarioName: string) => {
    stopPlayback()
    const replay = batchReplays.find(r => r.scenario_name === scenarioName)
    if (replay) {
      setState(prev => ({
        ...prev,
        activeSimulationId: replay.simulation_id,
        activeScenario: scenarioName,
        currentRoundIndex: 0,
        simulationReplay: replay,
      }))
    }
  }, [batchReplays, stopPlayback])

  const setRound = useCallback((index: number) => {
    setState(prev => ({
      ...prev,
      currentRoundIndex: Math.max(0, Math.min(index, maxRound)),
    }))
  }, [maxRound])

  const nextRound = useCallback(() => {
    setState(prev => ({
      ...prev,
      currentRoundIndex: Math.min(prev.currentRoundIndex + 1, maxRound),
    }))
  }, [maxRound])

  const prevRound = useCallback(() => {
    setState(prev => ({
      ...prev,
      currentRoundIndex: Math.max(prev.currentRoundIndex - 1, 0),
    }))
  }, [])

  const play = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    setState(prev => ({ ...prev, isReplayPlaying: true }))

    const intervalMs = DEFAULT_PLAYBACK_INTERVAL_MS / playbackSpeed

    intervalRef.current = setInterval(() => {
      setState(prev => {
        const nextIndex = prev.currentRoundIndex + 1
        if (nextIndex > maxRound) {
          if (intervalRef.current) clearInterval(intervalRef.current)
          intervalRef.current = null
          return { ...prev, isReplayPlaying: false }
        }
        return { ...prev, currentRoundIndex: nextIndex }
      })
    }, intervalMs)
  }, [maxRound, playbackSpeed])

  const pause = useCallback(() => {
    stopPlayback()
  }, [stopPlayback])

  const reset = useCallback(() => {
    stopPlayback()
    setState(prev => ({ ...prev, currentRoundIndex: 0 }))
  }, [stopPlayback])

  const setPlaybackSpeed = useCallback((speed: number) => {
    setPlaybackSpeedState(speed)
  }, [])

  const openPopup = useCallback(() => {
    setState(prev => ({ ...prev, isPopupOpen: true }))
  }, [])

  const closePopup = useCallback(() => {
    stopPlayback()
    setState(prev => ({ ...prev, isPopupOpen: false }))
  }, [stopPlayback])

  return {
    state,
    eventsUpToCurrentRound,
    currentRoundEvents,
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
    openPopup,
    closePopup,
    loading,
    error,
  }
}
