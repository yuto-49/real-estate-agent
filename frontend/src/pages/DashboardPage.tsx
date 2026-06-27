import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../utils/api'
import type { Property, UserProfile } from '../utils/types'
import UserProfileCard from '../components/UserProfileCard'
import DashboardMap from '../components/DashboardMap'
import UserFormModal from '../components/UserFormModal'

const SELECTED_USER_KEY = 'selectedUserId'

export default function DashboardPage() {
  const navigate = useNavigate()
  const [users, setUsers] = useState<UserProfile[]>([])
  const [selectedUserId, setSelectedUserId] = useState(
    () => localStorage.getItem(SELECTED_USER_KEY) || ''
  )
  const [loading, setLoading] = useState(true)
  const [properties, setProperties] = useState<Property[]>([])

  // Modal state
  const [showModal, setShowModal] = useState(false)
  const [editingUser, setEditingUser] = useState<UserProfile | null>(null)

  useEffect(() => {
    void loadUsers()
    void loadProperties()
  }, [])

  useEffect(() => {
    if (selectedUserId) {
      localStorage.setItem(SELECTED_USER_KEY, selectedUserId)
    }
  }, [selectedUserId])

  const loadUsers = async () => {
    setLoading(true)
    try {
      const data = await api.users.list()
      setUsers(data)
      if (!selectedUserId && data.length > 0) {
        setSelectedUserId(data[0].id)
      }
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const loadProperties = async () => {
    try {
      const data = await api.properties.list()
      setProperties(data.properties as Property[])
    } catch {
      setProperties([])
    }
  }

  const selectedUser = users.find((u) => u.id === selectedUserId) ?? null

  // Modal handlers
  const openCreate = () => {
    setEditingUser(null)
    setShowModal(true)
  }

  const openEdit = () => {
    setEditingUser(selectedUser)
    setShowModal(true)
  }

  const handleSaved = (saved: UserProfile) => {
    setShowModal(false)
    setEditingUser(null)
    // Refresh list and select saved user
    void loadUsers().then(() => {
      setSelectedUserId(saved.id)
    })
  }

  const handleDelete = async () => {
    if (!selectedUser) return
    if (!window.confirm(`Delete "${selectedUser.name}"? This cannot be undone.`)) return
    try {
      await api.users.delete(selectedUser.id)
      localStorage.removeItem(SELECTED_USER_KEY)
      setSelectedUserId('')
      void loadUsers()
    } catch {
      // ignore
    }
  }

  return (
    <div className="dashboard-page">
      <div className="page-title-row">
        <h2>Dashboard</h2>
      </div>

      {loading && <p>Loading...</p>}

      {!loading && (
        <div className="dashboard-map-layout">
          {/* Sidebar */}
          <div className="dashboard-sidebar">
            <div className="agent-control-group">
              <label>Active Investor Profile</label>
              <div className="user-selector-row">
                <select value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value)}>
                  <option value="">Select a user</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
                  ))}
                </select>
                <button className="primary-btn compact-btn" onClick={openCreate}>+ New</button>
              </div>
            </div>

            {selectedUser && (
              <UserProfileCard
                user={selectedUser}
                onEdit={openEdit}
                onDelete={handleDelete}
              />
            )}

            {!selectedUser && users.length === 0 && (
              <div className="empty-state-card">
                <p>No users yet.</p>
                <button className="primary-btn" onClick={openCreate}>Create Your First Account</button>
              </div>
            )}

            {/* Quick Actions */}
            <div className="dashboard-quick-actions">
              <h3>Quick Actions</h3>
              <div className="dashboard-action-buttons">
                <button className="primary-btn" onClick={() => navigate('/portfolio')}>
                  Open Portfolio
                </button>
              </div>
            </div>

            {/* Profile link */}
            {selectedUser && (
              <div className="dashboard-link-stack">
                <Link to={`/profile/${selectedUser.id}`} className="secondary-btn dashboard-link-btn">
                  View Full Profile
                </Link>
              </div>
            )}
          </div>

          {/* Map */}
          <DashboardMap
            properties={properties}
            selectedUser={selectedUser}
            onPropertyClick={() => navigate('/portfolio')}
          />
        </div>
      )}

      {/* User form modal */}
      {showModal && (
        <UserFormModal
          user={editingUser}
          onClose={() => { setShowModal(false); setEditingUser(null) }}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
