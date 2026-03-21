import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api } from '../utils/api'
import type { UserProfile, SimulationResult } from '../utils/types'
import UserFormModal from '../components/UserFormModal'

const SELECTED_USER_KEY = 'selectedUserId'

function formatCurrency(value: number | null | undefined): string {
  return typeof value === 'number' ? `$${value.toLocaleString()}` : 'N/A'
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function outcomeBadgeClass(outcome: string): string {
  switch (outcome) {
    case 'accepted': return 'ok'
    case 'rejected': return 'error'
    case 'max_rounds': return 'running'
    case 'broker_stopped': return 'running'
    default: return ''
  }
}

function outcomeLabel(outcome: string): string {
  switch (outcome) {
    case 'accepted': return 'Deal Reached'
    case 'rejected': return 'Rejected'
    case 'max_rounds': return 'Max Rounds'
    case 'broker_stopped': return 'Broker Stopped'
    default: return outcome
  }
}

export default function UserProfilePage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const [user, setUser] = useState<UserProfile | null>(null)
  const [simResults, setSimResults] = useState<SimulationResult[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [missingIdMessage, setMissingIdMessage] = useState('')

  useEffect(() => {
    let cancelled = false

    const resolveProfileRoute = async () => {
      if (id) return
      setLoading(true)
      setMissingIdMessage('')
      try {
        const users = await api.users.list()
        if (cancelled) return
        if (users.length === 0) {
          setMissingIdMessage('No users found. Create a profile from the dashboard first.')
          setLoading(false)
          return
        }
        const storedId = localStorage.getItem(SELECTED_USER_KEY)
        const targetId = storedId && users.some((u) => u.id === storedId)
          ? storedId
          : users[0].id
        localStorage.setItem(SELECTED_USER_KEY, targetId)
        navigate(`/profile/${targetId}`, { replace: true })
      } catch {
        if (cancelled) return
        setMissingIdMessage('Unable to select a profile. Open one from the dashboard.')
        setLoading(false)
      }
    }

    void resolveProfileRoute()
    return () => {
      cancelled = true
    }
  }, [id, navigate])

  useEffect(() => {
    if (!id) return
    setLoading(true)
    Promise.all([
      api.users.get(id).then((u) => setUser(u as UserProfile)),
      api.simulation.savedResults({ user_id: id }).then((data) => setSimResults(data.results as SimulationResult[])),
    ]).catch(() => {
      // ignore
    }).finally(() => setLoading(false))
  }, [id])

  const handleSaved = (saved: UserProfile) => {
    setShowModal(false)
    setUser(saved)
  }

  if (loading) return <div className="profile-page"><p>Loading...</p></div>
  if (!id) {
    return (
      <div className="profile-page">
        <p>{missingIdMessage || 'Select a profile from the dashboard.'} <Link to="/">Back to dashboard</Link></p>
      </div>
    )
  }
  if (!user) return <div className="profile-page"><p>User not found. <Link to="/">Back to dashboard</Link></p></div>

  // Stats
  const totalSims = simResults.length
  const deals = simResults.filter((s) => s.outcome === 'accepted')
  const dealsReached = deals.length
  const avgDealPrice = deals.length > 0
    ? deals.reduce((sum, d) => sum + (d.final_price ?? 0), 0) / deals.length
    : null
  const bestPrice = deals.length > 0
    ? Math.min(...deals.map((d) => d.final_price ?? Infinity))
    : null

  return (
    <div className="profile-page">
      {/* Header */}
      <div className="profile-header">
        <div className="profile-header-info">
          <div className="profile-avatar">
            {user.name.charAt(0).toUpperCase()}
          </div>
          <div>
            <h2>{user.name}</h2>
            <p className="profile-email">{user.email}</p>
            <span className={`status-pill ok`}>{user.role}</span>
            {user.created_at && (
              <p className="profile-member-since">Member since {new Date(user.created_at).toLocaleDateString()}</p>
            )}
          </div>
        </div>
        <div className="profile-header-actions">
          <button className="primary-btn" onClick={() => setShowModal(true)}>Edit Profile</button>
          <Link to="/" className="secondary-btn">Back to Dashboard</Link>
        </div>
      </div>

      {/* Stats Row */}
      <div className="profile-stats-row">
        <div className="profile-stat-card">
          <div className="profile-stat-value">{totalSims}</div>
          <div className="profile-stat-label">Total Simulations</div>
        </div>
        <div className="profile-stat-card">
          <div className="profile-stat-value">{dealsReached}</div>
          <div className="profile-stat-label">Deals Reached</div>
        </div>
        <div className="profile-stat-card">
          <div className="profile-stat-value">{avgDealPrice ? formatCurrency(Math.round(avgDealPrice)) : 'N/A'}</div>
          <div className="profile-stat-label">Avg Deal Price</div>
        </div>
        <div className="profile-stat-card">
          <div className="profile-stat-value">{bestPrice !== null ? formatCurrency(bestPrice) : 'N/A'}</div>
          <div className="profile-stat-label">Best Price</div>
        </div>
      </div>

      {/* Profile Details */}
      <div className="profile-details-card">
        <h3>Profile Details</h3>
        <div className="user-meta-grid">
          <div><label>Budget</label><p>{formatCurrency(user.budget_min)} - {formatCurrency(user.budget_max)}</p></div>
          <div><label>Timeline</label><p>{user.timeline_days ?? 'N/A'} days</p></div>
          <div><label>Risk Tolerance</label><p>{user.risk_tolerance || 'N/A'}</p></div>
          <div><label>Location</label><p>{user.zip_code || 'N/A'}{user.search_radius ? ` (${user.search_radius} mi radius)` : ''}</p></div>
          <div><label>Life Stage</label><p>{user.life_stage || 'N/A'}</p></div>
          <div><label>Preferred Types</label><p>{user.preferred_types.length ? user.preferred_types.join(', ') : 'N/A'}</p></div>
        </div>
      </div>

      {/* Simulation History */}
      <div className="profile-sim-history">
        <h3>Simulation History</h3>
        {simResults.length === 0 ? (
          <p style={{ color: '#888', fontSize: '0.85rem' }}>No simulations yet. <Link to="/simulation">Run one</Link>.</p>
        ) : (
          <div className="outcome-table-wrap">
            <table className="report-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Property</th>
                  <th>Scenario</th>
                  <th>Outcome</th>
                  <th>Asking</th>
                  <th>Final</th>
                  <th>Rounds</th>
                  <th>Discount</th>
                </tr>
              </thead>
              <tbody>
                {simResults.map((s) => {
                  const discount = s.final_price && s.asking_price
                    ? Math.round(((s.asking_price - s.final_price) / s.asking_price) * 100)
                    : null
                  return (
                    <tr key={s.id}>
                      <td>{formatDate(s.created_at)}</td>
                      <td className="report-id-cell">{s.property_id.slice(0, 10)}...</td>
                      <td>{s.scenario_name || s.strategy}</td>
                      <td>
                        <span className={`status-pill ${outcomeBadgeClass(s.outcome)}`}>
                          {outcomeLabel(s.outcome)}
                        </span>
                      </td>
                      <td>{formatCurrency(s.asking_price)}</td>
                      <td>{formatCurrency(s.final_price)}</td>
                      <td>{s.rounds_completed}</td>
                      <td>{discount !== null ? `${discount}%` : 'N/A'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal && (
        <UserFormModal
          user={user}
          onClose={() => setShowModal(false)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
