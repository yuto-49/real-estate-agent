import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api } from '../utils/api'

interface ChatMessage {
  id: number
  sender: 'user' | 'agent'
  role: string
  text: string
  tool_calls?: Array<{ tool: string; input: unknown; output: unknown }>
  timestamp: Date
}

interface UserOption {
  id: string
  name: string
  role: string
}

interface ReportOption {
  id: string
  status: string
  created_at?: string
  current_step: string
}

export default function NegotiationPage() {
  const { id: negotiationId } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const propertyId = searchParams.get('property_id')
  const propertyAddress = searchParams.get('address')
  const propertyPrice = searchParams.get('price')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [users, setUsers] = useState<UserOption[]>([])
  const [selectedUserId, setSelectedUserId] = useState('')
  const [selectedRole, setSelectedRole] = useState('buyer')
  const [error, setError] = useState('')
  const [reports, setReports] = useState<ReportOption[]>([])
  const [selectedReportId, setSelectedReportId] = useState<string>('')
  const [reportsLoading, setReportsLoading] = useState(false)

  useEffect(() => {
    void loadUsers()
  }, [])

  // Load reports when user changes
  useEffect(() => {
    if (selectedUserId) {
      void loadReports(selectedUserId)
    } else {
      setReports([])
      setSelectedReportId('')
    }
  }, [selectedUserId])

  const loadUsers = async () => {
    try {
      const data = await api.users.list()
      setUsers(data.map((u) => ({ id: u.id, name: u.name, role: u.role })))
      if (data.length > 0) setSelectedUserId(data[0].id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users')
    }
  }

  const loadReports = async (userId: string) => {
    setReportsLoading(true)
    try {
      const data = await api.reports.listByUser(userId)
      const completedReports = data.filter((r) => r.status === 'completed')
      setReports(completedReports)
      // Auto-select the most recent completed report
      if (completedReports.length > 0) {
        setSelectedReportId(completedReports[0].id)
      } else {
        setSelectedReportId('')
      }
    } catch {
      setReports([])
      setSelectedReportId('')
    } finally {
      setReportsLoading(false)
    }
  }

  const handleSend = async () => {
    if (!input.trim() || !selectedUserId || isLoading) return

    const userMsg: ChatMessage = {
      id: Date.now(),
      sender: 'user',
      role: selectedRole,
      text: input,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setIsLoading(true)
    setError('')

    try {
      let agentMessage = input
      if (propertyAddress && messages.length === 0) {
        agentMessage =
          `[Property Context]\nAddress: ${propertyAddress}\n` +
          (propertyPrice ? `Price: $${Number(propertyPrice).toLocaleString()}\n` : '') +
          (propertyId ? `Property ID: ${propertyId}\n` : '') +
          `\n[User Message]\n${input}`
      }
      const result = await api.agent.message({
        user_id: selectedUserId,
        role: selectedRole,
        message: agentMessage,
        report_id: selectedReportId || null,
      })

      if (result.error) {
        setError(result.error)
      } else {
        const agentMsg: ChatMessage = {
          id: Date.now() + 1,
          sender: 'agent',
          role: selectedRole,
          text: result.response,
          tool_calls: result.tool_calls,
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, agentMsg])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Agent request failed')
    } finally {
      setIsLoading(false)
    }
  }

  const selectedUser = users.find((u) => u.id === selectedUserId)

  const formatReportDate = (dateStr?: string) => {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="negotiation-page">
      <div className="page-title-row">
        <h2>Agent Chat{negotiationId ? ` — ${negotiationId.slice(0, 8)}...` : ''}</h2>
      </div>

      {/* Property Context Banner */}
      {propertyAddress && (
        <div className="report-active-banner" style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
          <strong>Property:</strong>
          <span>{propertyAddress}</span>
          {propertyPrice && <span style={{ fontWeight: 700 }}>${Number(propertyPrice).toLocaleString()}</span>}
          {propertyId && <span style={{ fontSize: '0.78rem', color: '#666' }}>ID: {propertyId}</span>}
        </div>
      )}

      {/* Agent Controls */}
      <div className="agent-controls">
        <div className="agent-control-group">
          <label>User</label>
          <select
            value={selectedUserId}
            onChange={(e) => setSelectedUserId(e.target.value)}
          >
            {users.map((u) => (
              <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
            ))}
          </select>
        </div>
        <div className="agent-control-group">
          <label>Agent Role</label>
          <select value={selectedRole} onChange={(e) => setSelectedRole(e.target.value)}>
            <option value="assistant">AI Assistant</option>
            <option value="buyer">Buyer Agent</option>
            <option value="seller">Seller Agent</option>
            <option value="broker">Broker Agent</option>
          </select>
        </div>
        <div className="agent-control-group">
          <label>Intelligence Report</label>
          {reportsLoading ? (
            <select disabled><option>Loading...</option></select>
          ) : reports.length === 0 ? (
            <select disabled>
              <option>No reports available</option>
            </select>
          ) : (
            <select
              value={selectedReportId}
              onChange={(e) => setSelectedReportId(e.target.value)}
            >
              <option value="">None (no report)</option>
              {reports.map((r) => (
                <option key={r.id} value={r.id}>
                  {formatReportDate(r.created_at) || r.id.slice(0, 8)}
                </option>
              ))}
            </select>
          )}
        </div>
        <div className="agent-control-group">
          <span className={`agent-status ${isLoading ? 'thinking' : 'ready'}`}>
            {isLoading ? 'Agent thinking...' : 'Ready'}
          </span>
        </div>
      </div>

      {/* Active Report Indicator */}
      {selectedReportId && (
        <div className="report-active-banner">
          Using intelligence report {selectedReportId.slice(0, 8)}... to inform agent decisions
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {/* Chat Messages */}
      <div className="agent-chat-messages">
        {messages.length === 0 && (
          <div className="agent-chat-empty">
            <p>Start a conversation with the {selectedRole} agent.</p>
            {reports.length > 0 && !selectedReportId && (
              <p className="agent-chat-hints">
                Tip: Select an intelligence report above to help the agent make data-driven decisions.
              </p>
            )}
            {reports.length === 0 && (
              <p className="agent-chat-hints">
                Tip: Generate an intelligence report from the Users page first for better investment advice.
              </p>
            )}
            <p className="agent-chat-hints">
              Try: "Find properties near an MRT station under $300k" or
              "How should I price my property?" or
              "What investment strategy do you recommend?"
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`agent-chat-msg ${msg.sender}`}>
            <div className="agent-chat-msg-header">
              <span className="agent-chat-sender">
                {msg.sender === 'user' ? (selectedUser?.name || 'You') : `${msg.role} agent`}
              </span>
              <span className="agent-chat-time">
                {msg.timestamp.toLocaleTimeString()}
              </span>
            </div>
            <div className="agent-chat-msg-body">
              {msg.text}
            </div>
            {msg.tool_calls && msg.tool_calls.length > 0 && (
              <div className="agent-chat-tools">
                <span className="agent-tools-label">Tools used:</span>
                {msg.tool_calls.map((tc, i) => (
                  <details key={i} className="agent-tool-detail">
                    <summary>{tc.tool}</summary>
                    <div className="agent-tool-io">
                      <div><strong>Input:</strong> <pre>{JSON.stringify(tc.input, null, 2)}</pre></div>
                      <div><strong>Output:</strong> <pre>{JSON.stringify(tc.output, null, 2)}</pre></div>
                    </div>
                  </details>
                ))}
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="agent-chat-msg agent">
            <div className="agent-chat-msg-header">
              <span className="agent-chat-sender">{selectedRole} agent</span>
            </div>
            <div className="agent-chat-msg-body agent-thinking">
              <span className="workflow-spinner" /> Thinking...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="agent-chat-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void handleSend()}
          placeholder={`Message the ${selectedRole} agent...`}
          disabled={isLoading || !selectedUserId}
        />
        <button onClick={() => void handleSend()} disabled={isLoading || !selectedUserId || !input.trim()}>
          {isLoading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  )
}
