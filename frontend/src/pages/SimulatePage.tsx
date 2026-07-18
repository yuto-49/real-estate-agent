import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import StepTimeline, {
  type TimelineStep,
} from '../components/simulation/StepTimeline'
import { buildWebSocketUrl } from '../config/runtime'
import { api } from '../utils/api'
import type { StrategyRunRecord } from '../utils/types'

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
  return buildWebSocketUrl(`/strategy/${runId}`)
}

function recordToSteps(record: StrategyRunRecord): TimelineStep[] {
  if (record.steps && record.steps.length > 0) {
    return record.steps.map((step) => ({
      type: step.type,
      label: step.label,
      detail: step.detail ?? null,
      at: step.at,
    }))
  }

  return [
    {
      type: 'stream.degraded',
      label: '進捗を確認しています',
      detail: 'ライブ配信が利用できないため、状態を定期確認しています。',
    },
  ]
}

export default function SimulatePage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [steps, setSteps] = useState<TimelineStep[]>([])
  const [status, setStatus] = useState<StreamStatus>('connecting')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const pollingRef = useRef<number | null>(null)

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    let usingPolling = false
    let terminal = false

    const stopPolling = () => {
      if (pollingRef.current !== null) {
        window.clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }

    const applyRecord = (record: StrategyRunRecord) => {
      setSteps(recordToSteps(record))
      if (record.status === 'failed') {
        terminal = true
        stopPolling()
        setStatus('error')
        setErrorMessage(record.error ?? 'シミュレーションの実行に失敗しました。')
        return
      }
      if (record.status === 'completed') {
        terminal = true
        stopPolling()
        setStatus('closed')
        setErrorMessage(null)
        return
      }
      setStatus('streaming')
      setErrorMessage(null)
    }

    const pollStatus = async () => {
      try {
        const record = await api.strategy.status(runId)
        if (cancelled) return
        applyRecord(record)
      } catch (err) {
        if (cancelled) return
        stopPolling()
        setStatus('error')
        setErrorMessage(err instanceof Error ? err.message : '進捗の取得に失敗しました。')
      }
    }

    const startPolling = () => {
      if (usingPolling || cancelled) return
      usingPolling = true
      setStatus('streaming')
      setErrorMessage(null)
      void pollStatus()
      pollingRef.current = window.setInterval(() => {
        void pollStatus()
      }, 1500)
    }

    const ws = new WebSocket(wsUrlFor(runId))
    wsRef.current = ws

    ws.onopen = () => {
      if (!cancelled) {
        setStatus('streaming')
        setErrorMessage(null)
      }
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
        terminal = true
        setStatus('error')
        setErrorMessage(parsed.payload?.detail_text ?? '配信エラーが発生しました。')
        return
      }
      if (parsed.type === 'stream.closed') {
        terminal = true
        stopPolling()
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
        startPolling()
      }
    }
    ws.onclose = () => {
      if (!cancelled && !usingPolling && !terminal) {
        startPolling()
      }
    }

    return () => {
      cancelled = true
      stopPolling()
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
      setErrorMessage(err instanceof Error ? err.message : '結果レポートを取得できませんでした。')
    }
  }

  return (
    <div className="simulate-page" data-testid="simulate-page">
      <header className="simulate-page__header">
        <h2>シミュレーション進行中</h2>
        <p className="onboarding-subtle">実行ID {runId}</p>
      </header>

      <StepTimeline steps={steps} status={status} errorMessage={errorMessage} />

      {status === 'closed' && (
        <button
          type="button"
          className="onboarding-primary"
          onClick={() => void handleViewReport()}
          data-testid="simulate-view-report"
        >
          統合レポートを見る
        </button>
      )}
    </div>
  )
}
