import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import StepTimeline, {
  type TimelineStep,
} from '../components/simulation/StepTimeline'
import { api } from '../utils/api'

type StreamStatus = 'connecting' | 'streaming' | 'closed' | 'error'

interface IncomingEvent {
  type: string
  payload?: {
    label?: string
    detail?: string | null
    at?: string
    status?: string
    reason?: string
    detail_text?: string
  }
}

function wsUrlFor(runId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/strategy/${runId}`
}

export default function SimulatePage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [steps, setSteps] = useState<TimelineStep[]>([])
  const [status, setStatus] = useState<StreamStatus>('connecting')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!runId) return
    let cancelled = false

    const ws = new WebSocket(wsUrlFor(runId))
    wsRef.current = ws

    ws.onopen = () => {
      if (!cancelled) setStatus('streaming')
    }
    ws.onmessage = (event) => {
      if (cancelled) return
      let parsed: IncomingEvent
      try {
        parsed = JSON.parse(event.data) as IncomingEvent
      } catch {
        return
      }
      if (parsed.type === 'error') {
        setStatus('error')
        setErrorMessage(parsed.payload?.detail_text ?? 'Stream error')
        return
      }
      if (parsed.type === 'stream.closed') {
        setStatus('closed')
        return
      }
      if (parsed.type === 'stream.degraded') {
        // Still streaming but via the slower polling fallback — no UI change.
        return
      }
      setSteps((prev) => [
        ...prev,
        {
          type: parsed.type,
          label: parsed.payload?.label ?? parsed.type,
          detail: parsed.payload?.detail ?? null,
          at: parsed.payload?.at,
        },
      ])
    }
    ws.onerror = () => {
      if (!cancelled) {
        setStatus('error')
        setErrorMessage('WebSocket connection failed.')
      }
    }
    ws.onclose = () => {
      if (!cancelled && status === 'streaming') setStatus('closed')
    }

    return () => {
      cancelled = true
      ws.close()
      wsRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])

  const handleViewReport = async () => {
    if (!runId) return
    try {
      const record = await api.strategy.result(runId)
      navigate(`/simulate/${runId}/report`, { state: { record } })
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Could not load result.')
    }
  }

  return (
    <div className="simulate-page" data-testid="simulate-page">
      <header className="simulate-page__header">
        <h2>Strategy run</h2>
        <p className="onboarding-subtle">Run ID {runId}</p>
      </header>

      <StepTimeline steps={steps} status={status} errorMessage={errorMessage} />

      {status === 'closed' && (
        <button
          type="button"
          className="onboarding-primary"
          onClick={() => void handleViewReport()}
          data-testid="simulate-view-report"
        >
          View unified report
        </button>
      )}
    </div>
  )
}
