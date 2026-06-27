import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api } from '../utils/api'
import type { UserProfile } from '../utils/types'
import UserFormModal from '../components/UserFormModal'

const SELECTED_USER_KEY = 'selectedUserId'

function formatCurrency(value: number | null | undefined): string {
  return typeof value === 'number' ? `$${value.toLocaleString()}` : 'N/A'
}

export default function UserProfilePage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const [user, setUser] = useState<UserProfile | null>(null)
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
    api.users
      .get(id)
      .then((u) => setUser(u as UserProfile))
      .catch(() => {
        // ignore
      })
      .finally(() => setLoading(false))
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
