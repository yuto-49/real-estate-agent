import { useState } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import type { WSEvent } from '../utils/types'

interface NegotiationChatProps {
  negotiationId: string
}

export default function NegotiationChat({ negotiationId }: NegotiationChatProps) {
  const [input, setInput] = useState('')
  const { isConnected, events, sendMessage } = useWebSocket({
    negotiationId,
    onEvent: (event: WSEvent) => {
      console.log('WS event:', event)
    },
  })

  const handleSend = () => {
    if (!input.trim()) return
    sendMessage({ type: 'message', text: input })
    setInput('')
  }

  return (
    <div className="negotiation-chat">
      <div className="chat-status">
        <span className={`indicator ${isConnected ? 'connected' : 'disconnected'}`} />
        {isConnected ? 'Connected' : 'Disconnected'}
      </div>

      <div className="chat-messages">
        {events.map((event, i) => (
          <div key={i} className={`message ${event.type}`}>
            <span className="event-type">{event.type}</span>
            <pre>{JSON.stringify(event, null, 2)}</pre>
          </div>
        ))}
      </div>

      <div className="chat-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Type a message..."
          disabled={!isConnected}
        />
        <button onClick={handleSend} disabled={!isConnected}>
          Send
        </button>
      </div>
    </div>
  )
}
