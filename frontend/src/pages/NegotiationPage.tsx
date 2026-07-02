import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useWebSocket } from '../hooks/useWebSocket'
import { api } from '../utils/api'
import { WSEventType } from '../utils/types'
import type {
  AgentResponseEvent,
  NegotiationEventReplayEntry,
  NegotiationOfferHistoryEntry,
  NegotiationSession,
  NegotiationTransitionAction,
  SocialSimAction,
  SocialSimResult,
  SocialSimStatus,
  SocialSimTimelineEntry,
  SocialSimTopic,
  WSEvent,
} from '../utils/types'

const SELECTED_USER_KEY = 'selectedUserId'
const DEFAULT_SOCIAL_TOPICS: SocialSimTopic[] = [
  'market_prices',
  'eviction_policy',
  'voucher_program',
  'neighborhood_safety',
]

const TRANSITION_OPTIONS: Array<{
  value: NegotiationTransitionAction
  label: string
}> = [
  { value: 'generate_contract', label: 'Generate Contract' },
  { value: 'schedule_inspection', label: 'Schedule Inspection' },
  { value: 'clear', label: 'Clear Contingencies' },
  { value: 'funds_transferred', label: 'Transfer Funds' },
  { value: 'reject', label: 'Reject Deal' },
  { value: 'withdraw', label: 'Withdraw' },
]

interface ChatMessage {
  id: number
  sender: 'user' | 'agent' | 'system'
  role: string
  text: string
  tool_calls?: Array<{ tool: string; input: unknown; output: unknown }>
  timestamp: Date
}

interface UserOption {
  id: string
  name: string
  role: string
  zip_code?: string | null
}

interface ReportOption {
  id: string
  status: string
  created_at?: string
  current_step: string
}

function formatCurrency(value?: number | null) {
  if (value == null || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('ja-JP', {
    style: 'currency',
    currency: 'JPY',
    maximumFractionDigits: 0,
  }).format(value)
}

function formatDateTime(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatStatusLabel(value?: string | null) {
  if (!value) return 'Unknown'
  return value.replace(/[_.]/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function extractZipCode(address?: string | null) {
  if (!address) return ''
  const match = address.match(/\b\d{5}(?:-\d{4})?\b/)
  return match?.[0] ?? ''
}

function topicLabel(topic: string) {
  return formatStatusLabel(topic)
}

function normalizeToolCalls(raw: Record<string, unknown>[] | undefined) {
  if (!raw) return []
  return raw.map((entry) => ({
    tool: typeof entry.tool === 'string' ? entry.tool : 'tool',
    input: entry.input ?? null,
    output: entry.output ?? null,
  }))
}

function socialStatusIsTerminal(status?: string | null) {
  return status === 'completed' || status === 'failed'
}

function eventSummary(event: NegotiationEventReplayEntry) {
  const payload = event.payload ?? {}
  if (typeof payload.message === 'string' && payload.message) return payload.message
  if (typeof payload.offer_price === 'number') return formatCurrency(payload.offer_price)
  if (typeof payload.final_price === 'number') return formatCurrency(payload.final_price)
  if (typeof payload.action === 'string') return formatStatusLabel(payload.action)
  return JSON.stringify(payload, null, 2)
}

export default function NegotiationPage() {
  const navigate = useNavigate()
  const { id: routeNegotiationId } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()

  const propertyId = searchParams.get('property_id') ?? ''
  const propertyAddress = searchParams.get('address') ?? ''
  const propertyPrice = searchParams.get('price')
  const propertyPriceNumber = propertyPrice ? Number(propertyPrice) : null

  const [users, setUsers] = useState<UserOption[]>([])
  const [reports, setReports] = useState<ReportOption[]>([])
  const [selectedBuyerId, setSelectedBuyerId] = useState(() => localStorage.getItem(SELECTED_USER_KEY) || '')
  const [selectedSellerId, setSelectedSellerId] = useState('')
  const [selectedReportId, setSelectedReportId] = useState('')
  const [reportsLoading, setReportsLoading] = useState(false)

  const [session, setSession] = useState<NegotiationSession | null>(null)
  const [sessionLoading, setSessionLoading] = useState(Boolean(routeNegotiationId))
  const [creatingSession, setCreatingSession] = useState(false)
  const [mutationLoading, setMutationLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [offerRole, setOfferRole] = useState<'buyer' | 'seller'>('buyer')
  const [offerPrice, setOfferPrice] = useState(propertyPriceNumber ? String(Math.round(propertyPriceNumber * 0.95)) : '')
  const [offerMessage, setOfferMessage] = useState('')

  const [acceptRole, setAcceptRole] = useState<'buyer' | 'seller'>('seller')
  const [acceptPrice, setAcceptPrice] = useState('')

  const [transitionAction, setTransitionAction] = useState<NegotiationTransitionAction>('generate_contract')
  const [transitionRole, setTransitionRole] = useState<'buyer' | 'seller' | 'broker'>('broker')
  const [transitionMessage, setTransitionMessage] = useState('')

  const [chatRole, setChatRole] = useState<'assistant' | 'buyer' | 'seller' | 'broker'>('buyer')
  const [chatInput, setChatInput] = useState('')
  const [chatPending, setChatPending] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])

  const [socialUserId, setSocialUserId] = useState('')
  const [socialZipCode, setSocialZipCode] = useState(extractZipCode(propertyAddress))
  const [socialIncomeBand, setSocialIncomeBand] = useState('')
  const [socialMaxRounds, setSocialMaxRounds] = useState('8')
  const [socialTopics, setSocialTopics] = useState<SocialSimTopic[]>(DEFAULT_SOCIAL_TOPICS)
  const [socialRunId, setSocialRunId] = useState('')
  const [socialLoading, setSocialLoading] = useState(false)
  const [socialError, setSocialError] = useState('')
  const [socialNotice, setSocialNotice] = useState('')
  const [socialStatus, setSocialStatus] = useState<SocialSimStatus | null>(null)
  const [socialActions, setSocialActions] = useState<SocialSimAction[]>([])
  const [socialTimeline, setSocialTimeline] = useState<SocialSimTimelineEntry[]>([])
  const [socialResult, setSocialResult] = useState<SocialSimResult | null>(null)

  const selectedBuyer = users.find((user) => user.id === selectedBuyerId)
  const selectedSeller = users.find((user) => user.id === selectedSellerId)
  const latestOffer = session?.offer_history[session.offer_history.length - 1]
  const displayAcceptPrice = acceptPrice || (latestOffer ? String(latestOffer.offer_price) : '')
  const activeNegotiationId = routeNegotiationId ?? session?.id

  const { isConnected, events: wsEvents, sendMessage } = useWebSocket({
    negotiationId: activeNegotiationId,
    onEvent: (event: WSEvent) => {
      if (event.type === WSEventType.AGENT_RESPONSE) {
        const agentEvent = event as AgentResponseEvent
        setChatPending(false)
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            sender: 'agent',
            role: agentEvent.agent_type,
            text: agentEvent.response,
            tool_calls: normalizeToolCalls(agentEvent.tool_calls),
            timestamp: new Date(agentEvent.timestamp),
          },
        ])
        return
      }

      if (event.type === WSEventType.SYSTEM_ERROR) {
        const detail = (event as WSEvent & { error?: string }).error ?? 'WebSocket error'
        setChatPending(false)
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            sender: 'system',
            role: 'system',
            text: detail,
            timestamp: new Date(event.timestamp),
          },
        ])
      }
    },
  })

  useEffect(() => {
    const loadUsers = async () => {
      try {
        const data = await api.users.list()
        const mapped = data.map((user) => ({
          id: user.id,
          name: user.name,
          role: user.role,
          zip_code: user.zip_code,
        }))
        setUsers(mapped)

        const buyers = mapped.filter((user) => user.role === 'buyer')
        const sellers = mapped.filter((user) => user.role === 'seller')

        if (!selectedBuyerId) {
          setSelectedBuyerId(buyers[0]?.id ?? mapped[0]?.id ?? '')
        } else if (!mapped.some((user) => user.id === selectedBuyerId)) {
          setSelectedBuyerId(buyers[0]?.id ?? mapped[0]?.id ?? '')
        }

        if (!selectedSellerId || !mapped.some((user) => user.id === selectedSellerId)) {
          const nextSeller = sellers.find((user) => user.id !== selectedBuyerId) ?? sellers[0] ?? mapped[0]
          setSelectedSellerId(nextSeller?.id ?? '')
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load users')
      }
    }

    void loadUsers()
  }, [])

  useEffect(() => {
    if (!selectedBuyerId) return

    localStorage.setItem(SELECTED_USER_KEY, selectedBuyerId)
    if (!socialUserId) setSocialUserId(selectedBuyerId)

    const loadReports = async () => {
      setReportsLoading(true)
      try {
        const data = await api.reports.listByUser(selectedBuyerId)
        const completedReports = data.filter((report) => report.status === 'completed')
        setReports(completedReports)
        if (completedReports.length > 0 && !completedReports.some((report) => report.id === selectedReportId)) {
          setSelectedReportId(completedReports[0].id)
        }
        if (completedReports.length === 0) {
          setSelectedReportId('')
        }
      } catch {
        setReports([])
        setSelectedReportId('')
      } finally {
        setReportsLoading(false)
      }
    }

    void loadReports()
  }, [selectedBuyerId])

  useEffect(() => {
    if (!socialZipCode && selectedBuyer?.zip_code) {
      setSocialZipCode(selectedBuyer.zip_code)
      return
    }

    if (!socialZipCode && propertyAddress) {
      setSocialZipCode(extractZipCode(propertyAddress))
    }
  }, [propertyAddress, selectedBuyer?.zip_code, socialZipCode])

  useEffect(() => {
    if (!routeNegotiationId) {
      setSession(null)
      setSessionLoading(false)
      return
    }

    let cancelled = false

    const loadSession = async (showSpinner: boolean) => {
      if (showSpinner) setSessionLoading(true)
      try {
        const data = await api.negotiations.get(routeNegotiationId)
        if (cancelled) return
        setSession(data)
        setError('')
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load negotiation session')
      } finally {
        if (!cancelled && showSpinner) setSessionLoading(false)
      }
    }

    void loadSession(true)
    const poller = window.setInterval(() => {
      void loadSession(false)
    }, 4000)

    return () => {
      cancelled = true
      window.clearInterval(poller)
    }
  }, [routeNegotiationId])

  useEffect(() => {
    if (!session) return
    setSelectedBuyerId(session.buyer_id)
    setSelectedSellerId(session.seller_id)
    setSocialUserId((current) => current || session.buyer_id)
    if (!offerPrice && latestOffer) {
      setOfferPrice(String(latestOffer.offer_price))
    }
  }, [latestOffer, offerPrice, session])

  useEffect(() => {
    setMessages([])
    setChatPending(false)
  }, [activeNegotiationId])

  useEffect(() => {
    if (!socialRunId) return

    let cancelled = false

    let poller = 0

    const refreshSocialRun = async () => {
      try {
        const [status, actions, timeline] = await Promise.all([
          api.socialSim.status(socialRunId),
          api.socialSim.actions(socialRunId, { limit: 12 }).catch(() => []),
          api.socialSim.timeline(socialRunId).then((data) => data.timeline).catch(() => []),
        ])

        if (cancelled) return

        setSocialStatus(status)
        setSocialActions(actions)
        setSocialTimeline(timeline)
        setSocialError(status.error_message ?? '')

        if (socialStatusIsTerminal(status.status)) {
          window.clearInterval(poller)
          const result = await api.socialSim.result(socialRunId).catch(() => null)
          if (!cancelled) {
            setSocialResult(result)
            if (status.status === 'completed') {
              setSocialNotice('Social interaction simulation completed and is now visible below.')
            }
          }
        }
      } catch (err) {
        if (cancelled) return
        setSocialError(err instanceof Error ? err.message : 'Failed to refresh social simulation')
      }
    }

    void refreshSocialRun()
    poller = window.setInterval(() => {
      void refreshSocialRun()
    }, 2500)

    return () => {
      cancelled = true
      window.clearInterval(poller)
    }
  }, [socialRunId])

  const handleCreateSession = async () => {
    if (!propertyId) {
      setError('Add a property_id in the URL query to create a negotiation session.')
      return
    }
    if (!selectedBuyerId || !selectedSellerId) {
      setError('Select both a buyer and seller before starting the session.')
      return
    }

    setCreatingSession(true)
    setError('')
    setNotice('')

    try {
      const negotiation = await api.negotiations.start({
        property_id: propertyId,
        buyer_id: selectedBuyerId,
        seller_id: selectedSellerId,
      })
      const query = searchParams.toString()
      navigate(`/negotiate/${negotiation.id}${query ? `?${query}` : ''}`)
      setNotice('Negotiation session started.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create negotiation session')
    } finally {
      setCreatingSession(false)
    }
  }

  const refreshSession = async () => {
    if (!activeNegotiationId) return
    const data = await api.negotiations.get(activeNegotiationId)
    setSession(data)
  }

  const handleOfferSubmit = async () => {
    if (!activeNegotiationId) {
      setError('Start a negotiation session before sending an offer.')
      return
    }
    if (!offerPrice) {
      setError('Enter an offer price.')
      return
    }

    setMutationLoading(true)
    setError('')
    setNotice('')

    try {
      await api.negotiations.offer(activeNegotiationId, {
        offer_price: Number(offerPrice),
        from_role: offerRole,
        message: offerMessage,
      })
      await refreshSession()
      setNotice(`${formatStatusLabel(offerRole)} offer submitted.`)
      setOfferMessage('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit offer')
    } finally {
      setMutationLoading(false)
    }
  }

  const handleAcceptSubmit = async () => {
    if (!activeNegotiationId) {
      setError('Start a negotiation session before accepting an offer.')
      return
    }
    if (!displayAcceptPrice) {
      setError('There is no active price to accept yet.')
      return
    }

    setMutationLoading(true)
    setError('')
    setNotice('')

    try {
      await api.negotiations.accept(activeNegotiationId, {
        from_role: acceptRole,
        final_price: Number(displayAcceptPrice),
      })
      await refreshSession()
      setNotice('Offer accepted.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to accept offer')
    } finally {
      setMutationLoading(false)
    }
  }

  const handleTransitionSubmit = async () => {
    if (!activeNegotiationId) {
      setError('Start a negotiation session before moving lifecycle state.')
      return
    }

    setMutationLoading(true)
    setError('')
    setNotice('')

    try {
      await api.negotiations.transition(activeNegotiationId, {
        action: transitionAction,
        from_role: transitionRole,
        message: transitionMessage,
      })
      await refreshSession()
      setNotice(`${formatStatusLabel(transitionAction)} applied.`)
      setTransitionMessage('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to transition negotiation')
    } finally {
      setMutationLoading(false)
    }
  }

  const handleSendAgentMessage = () => {
    const activeUserId =
      chatRole === 'seller'
        ? selectedSellerId || session?.seller_id || ''
        : selectedBuyerId || session?.buyer_id || ''

    if (!activeNegotiationId || !activeUserId || !chatInput.trim()) return

    const nextText = chatInput.trim()
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        sender: 'user',
        role: chatRole,
        text: nextText,
        timestamp: new Date(),
      },
    ])
    setChatInput('')
    setChatPending(true)

    sendMessage({
      user_id: activeUserId,
      role: chatRole,
      text: nextText,
      report_id: selectedReportId || null,
    })
  }

  const handleToggleTopic = (topic: SocialSimTopic) => {
    setSocialTopics((current) => {
      if (current.includes(topic)) {
        return current.filter((entry) => entry !== topic)
      }
      return [...current, topic]
    })
  }

  const handleStartSocialSim = async () => {
    if (!socialUserId) {
      setSocialError('Select a trigger user before starting the social simulation.')
      return
    }
    if (socialTopics.length === 0) {
      setSocialError('Select at least one topic to simulate.')
      return
    }

    setSocialLoading(true)
    setSocialError('')
    setSocialNotice('')
    setSocialResult(null)
    setSocialTimeline([])
    setSocialActions([])

    try {
      const result = await api.socialSim.start({
        user_id: socialUserId,
        zip_code: socialZipCode || undefined,
        income_band: socialIncomeBand || undefined,
        max_rounds: Number(socialMaxRounds) || 8,
        topics: socialTopics,
      })
      setSocialRunId(result.run_id)
      setSocialStatus({
        id: result.run_id,
        status: result.status,
        current_round: 0,
        total_rounds: Number(socialMaxRounds) || 8,
        action_count: 0,
      })
      setSocialNotice(result.message)
    } catch (err) {
      setSocialError(err instanceof Error ? err.message : 'Failed to start social simulation')
    } finally {
      setSocialLoading(false)
    }
  }

  const visibleEvents = session?.events.slice(-8).reverse() ?? []
  const visibleOffers = session?.offer_history.slice().reverse() ?? []
  const visibleSocialActions = socialActions.slice().reverse()
  const visibleWsEvents = wsEvents.slice(-8).reverse()

  return (
    <div className="negotiation-page">
      <div className="page-title-row">
        <h2>Negotiation Session</h2>
        {activeNegotiationId && <span className="negotiation-id-badge">{activeNegotiationId.slice(0, 8)}...</span>}
      </div>

      {propertyAddress && (
        <div className="report-active-banner negotiation-property-banner">
          <strong>Property</strong>
          <span>{propertyAddress}</span>
          {propertyPriceNumber != null && <span className="negotiation-property-price">{formatCurrency(propertyPriceNumber)}</span>}
          {propertyId && <span className="negotiation-property-meta">ID: {propertyId}</span>}
        </div>
      )}

      {(error || notice) && (
        <div className={`negotiation-feedback ${error ? 'error' : 'success'}`}>
          {error || notice}
        </div>
      )}

      <div className="negotiation-shell">
        <div className="negotiation-main-column">
          <section className="negotiation-surface">
            <div className="negotiation-section-header">
              <div>
                <h3>Session Setup</h3>
                <p>REST is the source of truth for session state. Create or reload a negotiation here.</p>
              </div>
              {activeNegotiationId && (
                <button className="secondary-btn" onClick={() => void refreshSession()} disabled={sessionLoading || mutationLoading}>
                  Refresh Session
                </button>
              )}
            </div>

            <div className="agent-controls">
              <div className="agent-control-group">
                <label>Buyer</label>
                <select value={selectedBuyerId} onChange={(event) => setSelectedBuyerId(event.target.value)}>
                  <option value="">Select buyer</option>
                  {users
                    .filter((user) => user.role === 'buyer' || !users.some((entry) => entry.role === 'buyer'))
                    .map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.name} ({user.role})
                      </option>
                    ))}
                </select>
              </div>

              <div className="agent-control-group">
                <label>Seller</label>
                <select value={selectedSellerId} onChange={(event) => setSelectedSellerId(event.target.value)}>
                  <option value="">Select seller</option>
                  {users
                    .filter((user) => user.role === 'seller' || !users.some((entry) => entry.role === 'seller'))
                    .map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.name} ({user.role})
                      </option>
                    ))}
                </select>
              </div>

              <div className="agent-control-group">
                <label>Intelligence Report</label>
                {reportsLoading ? (
                  <select disabled>
                    <option>Loading...</option>
                  </select>
                ) : reports.length === 0 ? (
                  <select disabled>
                    <option>No completed reports</option>
                  </select>
                ) : (
                  <select value={selectedReportId} onChange={(event) => setSelectedReportId(event.target.value)}>
                    <option value="">None</option>
                    {reports.map((report) => (
                      <option key={report.id} value={report.id}>
                        {formatDateTime(report.created_at) || report.id.slice(0, 8)}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="agent-control-group">
                <label>Live Socket</label>
                <span className={`agent-status ${isConnected ? 'ready' : 'thinking'}`}>
                  {isConnected ? 'Connected' : activeNegotiationId ? 'Connecting...' : 'Session required'}
                </span>
              </div>
            </div>

            {!activeNegotiationId && (
              <div className="negotiation-empty-state">
                <p>This page now works from a negotiation session, not generic agent chat.</p>
                <p>Start a session to unlock canonical state, typed actions, event replay, and live agent sidecar messaging.</p>
                <button className="secondary-btn" onClick={() => void handleCreateSession()} disabled={creatingSession || !propertyId}>
                  {creatingSession ? 'Starting…' : 'Start Negotiation Session'}
                </button>
              </div>
            )}
          </section>

          {sessionLoading && activeNegotiationId && (
            <section className="negotiation-surface">
              <p>Loading negotiation session…</p>
            </section>
          )}

          {session && (
            <>
              <section className="negotiation-surface">
                <div className="negotiation-section-header">
                  <div>
                    <h3>Session State</h3>
                    <p>The canonical read model from <code>GET /api/negotiations/{session.id}</code>.</p>
                  </div>
                </div>

                <div className="negotiation-summary-grid">
                  <div className="negotiation-stat-card">
                    <span>Status</span>
                    <strong>{formatStatusLabel(session.status)}</strong>
                  </div>
                  <div className="negotiation-stat-card">
                    <span>Round Count</span>
                    <strong>{session.round_count}</strong>
                  </div>
                  <div className="negotiation-stat-card">
                    <span>Deadline</span>
                    <strong>{formatDateTime(session.deadline_at)}</strong>
                  </div>
                  <div className="negotiation-stat-card">
                    <span>Latest Price</span>
                    <strong>{formatCurrency(latestOffer?.offer_price ?? session.final_price)}</strong>
                  </div>
                </div>
              </section>

              <section className="negotiation-surface">
                <div className="negotiation-section-header">
                  <div>
                    <h3>Typed Actions</h3>
                    <p>Offer, accept, and lifecycle transitions now go through typed REST bodies instead of ad hoc chat.</p>
                  </div>
                </div>

                <div className="negotiation-actions-grid">
                  <div className="negotiation-action-card">
                    <h4>Submit Offer</h4>
                    <label>Actor</label>
                    <select value={offerRole} onChange={(event) => setOfferRole(event.target.value as 'buyer' | 'seller')}>
                      <option value="buyer">Buyer</option>
                      <option value="seller">Seller</option>
                    </select>
                    <label>Offer Price</label>
                    <input type="number" value={offerPrice} onChange={(event) => setOfferPrice(event.target.value)} placeholder="385000" />
                    <label>Message</label>
                    <textarea value={offerMessage} onChange={(event) => setOfferMessage(event.target.value)} placeholder="Explain the reasoning behind this move." />
                    <button onClick={() => void handleOfferSubmit()} disabled={mutationLoading}>
                      {mutationLoading ? 'Submitting…' : 'Submit Offer'}
                    </button>
                  </div>

                  <div className="negotiation-action-card">
                    <h4>Accept Offer</h4>
                    <label>Actor</label>
                    <select value={acceptRole} onChange={(event) => setAcceptRole(event.target.value as 'buyer' | 'seller')}>
                      <option value="seller">Seller</option>
                      <option value="buyer">Buyer</option>
                    </select>
                    <label>Final Price</label>
                    <input
                      type="number"
                      value={acceptPrice}
                      onChange={(event) => setAcceptPrice(event.target.value)}
                      placeholder={latestOffer ? String(latestOffer.offer_price) : 'Use latest offer'}
                    />
                    <p className="negotiation-helper-text">If you leave this blank, the latest live offer will be accepted.</p>
                    <button onClick={() => void handleAcceptSubmit()} disabled={mutationLoading}>
                      {mutationLoading ? 'Accepting…' : 'Accept Offer'}
                    </button>
                  </div>

                  <div className="negotiation-action-card">
                    <h4>Transition Lifecycle</h4>
                    <label>Action</label>
                    <select value={transitionAction} onChange={(event) => setTransitionAction(event.target.value as NegotiationTransitionAction)}>
                      {TRANSITION_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <label>Actor</label>
                    <select value={transitionRole} onChange={(event) => setTransitionRole(event.target.value as 'buyer' | 'seller' | 'broker')}>
                      <option value="broker">Broker</option>
                      <option value="buyer">Buyer</option>
                      <option value="seller">Seller</option>
                    </select>
                    <label>Message</label>
                    <textarea value={transitionMessage} onChange={(event) => setTransitionMessage(event.target.value)} placeholder="Explain why the session is moving forward." />
                    <button onClick={() => void handleTransitionSubmit()} disabled={mutationLoading}>
                      {mutationLoading ? 'Updating…' : 'Apply Transition'}
                    </button>
                  </div>
                </div>
              </section>

              <section className="negotiation-detail-grid">
                <div className="negotiation-surface">
                  <div className="negotiation-section-header">
                    <div>
                      <h3>Current Analysis</h3>
                      <p>Session analysis from the decision/outcome domain layer.</p>
                    </div>
                  </div>

                  <div className="negotiation-analysis-grid">
                    <div className="negotiation-analysis-row">
                      <span>Recommendation</span>
                      <strong>{session.current_analysis.recommendation ?? '—'}</strong>
                    </div>
                    <div className="negotiation-analysis-row">
                      <span>Suggested Price</span>
                      <strong>{formatCurrency(session.current_analysis.suggested_price)}</strong>
                    </div>
                    <div className="negotiation-analysis-row">
                      <span>Spread</span>
                      <strong>
                        {session.current_analysis.spread_percent != null
                          ? `${session.current_analysis.spread_percent.toFixed(2)}%`
                          : '—'}
                      </strong>
                    </div>
                    <div className="negotiation-analysis-row">
                      <span>ZOPA Detected</span>
                      <strong>{session.current_analysis.zopa_detected == null ? '—' : session.current_analysis.zopa_detected ? 'Yes' : 'No'}</strong>
                    </div>
                    <div className="negotiation-analysis-row">
                      <span>Broker Mediation</span>
                      <strong>
                        {session.current_analysis.broker_mediation_recommended == null
                          ? '—'
                          : session.current_analysis.broker_mediation_recommended
                            ? 'Recommended'
                            : 'Not Needed'}
                      </strong>
                    </div>
                  </div>

                  <details className="negotiation-json-details">
                    <summary>View full analysis payload</summary>
                    <pre>{JSON.stringify(session.current_analysis, null, 2)}</pre>
                  </details>
                </div>

                <div className="negotiation-surface">
                  <div className="negotiation-section-header">
                    <div>
                      <h3>Offer History</h3>
                      <p>Every recorded offer and counter in this session ledger.</p>
                    </div>
                  </div>

                  <div className="negotiation-list">
                    {visibleOffers.length === 0 ? (
                      <p className="negotiation-empty-copy">No offers yet.</p>
                    ) : (
                      visibleOffers.map((offer: NegotiationOfferHistoryEntry) => (
                        <div key={offer.id} className="negotiation-list-item">
                          <div className="negotiation-list-head">
                            <strong>{formatCurrency(offer.offer_price)}</strong>
                            <span>{formatStatusLabel(offer.actor_role)}</span>
                          </div>
                          <div className="negotiation-list-meta">
                            <span>{formatDateTime(offer.created_at)}</span>
                            {offer.status && <span>{formatStatusLabel(offer.status)}</span>}
                          </div>
                          {offer.message && <p>{offer.message}</p>}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </section>

              <section className="negotiation-detail-grid">
                <div className="negotiation-surface">
                  <div className="negotiation-section-header">
                    <div>
                      <h3>Event Replay</h3>
                      <p>Canonical event stream for the negotiation aggregate.</p>
                    </div>
                  </div>

                  <div className="negotiation-list">
                    {visibleEvents.length === 0 ? (
                      <p className="negotiation-empty-copy">No domain events recorded yet.</p>
                    ) : (
                      visibleEvents.map((event) => (
                        <div key={`${event.sequence}-${event.event_type}`} className="negotiation-list-item">
                          <div className="negotiation-list-head">
                            <strong>{formatStatusLabel(event.event_type)}</strong>
                            <span>#{event.sequence}</span>
                          </div>
                          <div className="negotiation-list-meta">
                            <span>{event.actor_type ? `${formatStatusLabel(event.actor_type)}${event.actor_id ? ` · ${event.actor_id.slice(0, 8)}` : ''}` : 'System'}</span>
                            <span>{formatDateTime(event.created_at)}</span>
                          </div>
                          <pre>{eventSummary(event)}</pre>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="negotiation-surface">
                  <div className="negotiation-section-header">
                    <div>
                      <h3>Live WebSocket Feed</h3>
                      <p>Negotiation-scoped live events and agent commentary.</p>
                    </div>
                  </div>

                  <div className="negotiation-list">
                    {visibleWsEvents.length === 0 ? (
                      <p className="negotiation-empty-copy">No live socket events yet.</p>
                    ) : (
                      visibleWsEvents.map((event, index) => (
                        <div key={`${event.type}-${event.timestamp}-${index}`} className="negotiation-list-item">
                          <div className="negotiation-list-head">
                            <strong>{formatStatusLabel(event.type)}</strong>
                            <span>{formatDateTime(event.timestamp)}</span>
                          </div>
                          <pre>{JSON.stringify(event, null, 2)}</pre>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </section>
            </>
          )}

          <section className="negotiation-surface">
            <div className="negotiation-section-header">
              <div>
                <h3>Social Interaction Simulation</h3>
                <p>This is now visible during the run: status, live actions, topic trajectory, and final narrative output.</p>
              </div>
              {socialRunId && <span className="negotiation-id-badge">{socialRunId.slice(0, 8)}...</span>}
            </div>

            {(socialError || socialNotice) && (
              <div className={`negotiation-feedback ${socialError ? 'error' : 'success'}`}>
                {socialError || socialNotice}
              </div>
            )}

            <div className="negotiation-actions-grid">
              <div className="negotiation-action-card">
                <h4>Run Configuration</h4>
                <label>Trigger User</label>
                <select value={socialUserId} onChange={(event) => setSocialUserId(event.target.value)}>
                  <option value="">Select user</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.name} ({user.role})
                    </option>
                  ))}
                </select>
                <label>Zip Code</label>
                <input type="text" value={socialZipCode} onChange={(event) => setSocialZipCode(event.target.value)} placeholder="1730004" />
                <label>Income Band</label>
                <select value={socialIncomeBand} onChange={(event) => setSocialIncomeBand(event.target.value)}>
                  <option value="">All income bands</option>
                  <option value="low">Low</option>
                  <option value="moderate">Moderate</option>
                  <option value="middle">Middle</option>
                  <option value="upper">Upper</option>
                </select>
                <label>Max Rounds</label>
                <input type="number" min="1" max="25" value={socialMaxRounds} onChange={(event) => setSocialMaxRounds(event.target.value)} />
                <button onClick={() => void handleStartSocialSim()} disabled={socialLoading}>
                  {socialLoading ? 'Starting…' : 'Start Social Simulation'}
                </button>
              </div>

              <div className="negotiation-action-card">
                <h4>Topics</h4>
                <div className="negotiation-topic-grid">
                  {DEFAULT_SOCIAL_TOPICS.map((topic) => (
                    <label key={topic} className="negotiation-topic-option">
                      <input
                        type="checkbox"
                        checked={socialTopics.includes(topic)}
                        onChange={() => handleToggleTopic(topic)}
                      />
                      <span>{topicLabel(topic)}</span>
                    </label>
                  ))}
                </div>
                <p className="negotiation-helper-text">
                  The panel below will update while the simulation is running, so you can watch the household reaction system evolve in real time.
                </p>
              </div>

              <div className="negotiation-action-card">
                <h4>Run Status</h4>
                <div className="negotiation-analysis-grid">
                  <div className="negotiation-analysis-row">
                    <span>Status</span>
                    <strong>{formatStatusLabel(socialStatus?.status ?? 'idle')}</strong>
                  </div>
                  <div className="negotiation-analysis-row">
                    <span>Current Round</span>
                    <strong>{socialStatus?.current_round ?? 0}</strong>
                  </div>
                  <div className="negotiation-analysis-row">
                    <span>Total Rounds</span>
                    <strong>{socialStatus?.total_rounds ?? 0}</strong>
                  </div>
                  <div className="negotiation-analysis-row">
                    <span>Action Count</span>
                    <strong>{socialStatus?.action_count ?? 0}</strong>
                  </div>
                </div>
                {socialStatus?.error_message && <p className="negotiation-helper-text error">{socialStatus.error_message}</p>}
              </div>
            </div>

            <div className="negotiation-detail-grid">
              <div className="negotiation-surface negotiation-surface-nested">
                <div className="negotiation-section-header">
                  <div>
                    <h3>Live Social Actions</h3>
                    <p>Latest household reactions as the simulation runs.</p>
                  </div>
                </div>

                <div className="negotiation-list">
                  {visibleSocialActions.length === 0 ? (
                    <p className="negotiation-empty-copy">Start a social simulation to watch household actions appear here.</p>
                  ) : (
                    visibleSocialActions.map((action) => (
                      <div key={action.id} className="negotiation-list-item">
                        <div className="negotiation-list-head">
                          <strong>Round {action.round_num}</strong>
                          <span>{topicLabel(action.topic)}</span>
                        </div>
                        <div className="negotiation-list-meta">
                          <span>{formatStatusLabel(action.action_type)}</span>
                          <span>{action.sentiment_value != null ? action.sentiment_value.toFixed(2) : '—'}</span>
                        </div>
                        <p>{action.content || 'No narrative content for this action.'}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="negotiation-surface negotiation-surface-nested">
                <div className="negotiation-section-header">
                  <div>
                    <h3>Topic Timeline</h3>
                    <p>Round-by-round movement across the tracked social topics.</p>
                  </div>
                </div>

                <div className="negotiation-list">
                  {socialTimeline.length === 0 ? (
                    <p className="negotiation-empty-copy">Timeline points will appear as actions accumulate.</p>
                  ) : (
                    socialTimeline.map((entry) => (
                      <div key={`${entry.round_num}-${entry.topic}`} className="negotiation-list-item">
                        <div className="negotiation-list-head">
                          <strong>Round {entry.round_num}</strong>
                          <span>{topicLabel(entry.topic)}</span>
                        </div>
                        <div className="negotiation-list-meta">
                          <span>{formatStatusLabel(entry.dominant_stance)}</span>
                          <span>{entry.action_count} actions</span>
                        </div>
                        <p>Average sentiment: {entry.avg_sentiment.toFixed(2)}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            {socialResult && (
              <div className="negotiation-workflow">
                <div className="negotiation-section-header">
                  <div>
                    <h3>Final Simulation Output</h3>
                    <p>The completed social reaction state that can feed downstream reporting and negotiation logic.</p>
                  </div>
                </div>

                <div className="negotiation-detail-grid">
                  <div className="negotiation-surface negotiation-surface-nested">
                    <h4>Narrative Output</h4>
                    <pre>{JSON.stringify(socialResult.narrative_output, null, 2)}</pre>
                  </div>
                  <div className="negotiation-surface negotiation-surface-nested">
                    <h4>Sentiment Delta</h4>
                    <pre>{JSON.stringify(socialResult.sentiment_delta, null, 2)}</pre>
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>

        <aside className="negotiation-side-column">
          <section className="negotiation-surface">
            <div className="negotiation-section-header">
              <div>
                <h3>Agent Sidecar</h3>
                <p>Useful for commentary and tools, but no longer the primary mutation path.</p>
              </div>
            </div>

            <div className="agent-controls">
              <div className="agent-control-group">
                <label>Agent Role</label>
                <select value={chatRole} onChange={(event) => setChatRole(event.target.value as 'assistant' | 'buyer' | 'seller' | 'broker')}>
                  <option value="assistant">AI Assistant</option>
                  <option value="buyer">Buyer Side</option>
                  <option value="seller">Seller Side</option>
                  <option value="broker">Broker Coach</option>
                </select>
              </div>
              <div className="agent-control-group">
                <label>Active Buyer</label>
                <span className="negotiation-inline-copy">{selectedBuyer?.name ?? 'Not selected'}</span>
              </div>
              <div className="agent-control-group">
                <label>Active Seller</label>
                <span className="negotiation-inline-copy">{selectedSeller?.name ?? 'Not selected'}</span>
              </div>
            </div>

            <div className="agent-chat-messages">
              {messages.length === 0 ? (
                <div className="agent-chat-empty">
                  <p>Use the sidecar for live reasoning and tool-assisted commentary.</p>
                  <div className="agent-chat-hints">
                    Session state, offers, transitions, and social reactions are now visible elsewhere on the page while the agent remains a support channel.
                  </div>
                </div>
              ) : (
                messages.map((message) => (
                  <div key={message.id} className={`agent-chat-msg ${message.sender === 'user' ? 'user' : message.sender === 'agent' ? 'agent' : ''}`}>
                    <div className="agent-chat-msg-header">
                      <span className="agent-chat-sender">{message.role}</span>
                      <span className="agent-chat-time">{message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div className="agent-chat-msg-body">{message.text}</div>
                    {message.tool_calls && message.tool_calls.length > 0 && (
                      <div className="agent-chat-tools">
                        <span className="agent-tools-label">Tools used</span>
                        {message.tool_calls.map((toolCall, index) => (
                          <details key={`${message.id}-${index}`} className="agent-tool-detail">
                            <summary>{toolCall.tool}</summary>
                            <div className="agent-tool-io">
                              <div>
                                <strong>Input</strong>
                                <pre>{JSON.stringify(toolCall.input, null, 2)}</pre>
                              </div>
                              <div>
                                <strong>Output</strong>
                                <pre>{JSON.stringify(toolCall.output, null, 2)}</pre>
                              </div>
                            </div>
                          </details>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}

              {chatPending && (
                <div className="agent-chat-msg agent">
                  <div className="agent-chat-msg-header">
                    <span className="agent-chat-sender">{chatRole}</span>
                  </div>
                  <div className="agent-chat-msg-body agent-thinking">
                    <span className="workflow-spinner" /> Thinking...
                  </div>
                </div>
              )}
            </div>

            <div className="agent-chat-input">
              <input
                type="text"
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') handleSendAgentMessage()
                }}
                placeholder={activeNegotiationId ? `Message the ${chatRole} agent...` : 'Start a session to use live agent chat'}
                disabled={!activeNegotiationId || chatPending}
              />
              <button onClick={handleSendAgentMessage} disabled={!activeNegotiationId || chatPending || !chatInput.trim()}>
                {chatPending ? 'Sending…' : 'Send'}
              </button>
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}
