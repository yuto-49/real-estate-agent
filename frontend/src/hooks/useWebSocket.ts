import { useCallback, useEffect, useRef, useState } from 'react'
import type { WSEvent } from '../utils/types'

interface UseWebSocketOptions {
  negotiationId: string
  onEvent?: (event: WSEvent) => void
  reconnectInterval?: number
  maxRetries?: number
}

interface UseWebSocketReturn {
  isConnected: boolean
  lastEvent: WSEvent | null
  events: WSEvent[]
  sendMessage: (data: unknown) => void
}

export function useWebSocket({
  negotiationId,
  onEvent,
  reconnectInterval = 3000,
  maxRetries = 5,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null)
  const [events, setEvents] = useState<WSEvent[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>()

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/negotiation/${negotiationId}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      retriesRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WSEvent
        setLastEvent(data)
        setEvents((prev) => [...prev, data])
        onEvent?.(data)
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => {
      setIsConnected(false)
      if (retriesRef.current < maxRetries) {
        retriesRef.current += 1
        reconnectTimerRef.current = setTimeout(connect, reconnectInterval)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [negotiationId, onEvent, reconnectInterval, maxRetries])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const sendMessage = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  return { isConnected, lastEvent, events, sendMessage }
}
