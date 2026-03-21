import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../utils/api'
import type { Property, UserProfile, SimulationResult } from '../utils/types'
import UserProfileCard from '../components/UserProfileCard'
import DashboardMap from '../components/DashboardMap'
import UserFormModal from '../components/UserFormModal'

const SELECTED_USER_KEY = 'selectedUserId'

interface ReportMini {
  id: string
  status: string
  progress: number
  created_at?: string
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [users, setUsers] = useState<UserProfile[]>([])
  const [selectedUserId, setSelectedUserId] = useState(
    () => localStorage.getItem(SELECTED_USER_KEY) || ''
  )
  const [loading, setLoading] = useState(true)
  const [reports, setReports] = useState<ReportMini[]>([])
  const [properties, setProperties] = useState<Property[]>([])
  const [savedSims, setSavedSims] = useState<SimulationResult[]>([])
  const [selectedSimBatch, setSelectedSimBatch] = useState<string>('all')

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
      void loadReports(selectedUserId)
      void loadSavedSims(selectedUserId)
    } else {
      setSavedSims([])
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

  const loadSavedSims = async (userId: string) => {
    try {
      const data = await api.simulation.savedResults({ user_id: userId })
      setSavedSims(data.results as SimulationResult[])
      setSelectedSimBatch('all')
    } catch {
      setSavedSims([])
    }
  }

  const loadReports = async (userId: string) => {
    try {
      const data = await api.reports.listByUser(userId)
      setReports(data.slice(0, 5).map((r) => ({
        id: r.id,
        status: r.status,
        progress: r.progress,
        created_at: r.created_at,
      })))
    } catch {
      setReports([])
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
      setReports([])
      void loadUsers()
    } catch {
      // ignore
    }
  }

  function formatDate(dateStr?: string): string {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
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
                <button className="primary-btn" onClick={() => navigate('/analysis')}>
                  Generate Report
                </button>
                <button className="primary-btn" style={{ background: '#3a3a6e' }} onClick={() => navigate('/simulation')}>
                  Run Simulation
                </button>
              </div>
            </div>

            {/* Simulation Selector */}
            {selectedUser && savedSims.length > 0 && (
              <div className="agent-control-group">
                <label>Saved Simulations ({savedSims.length})</label>
                <select
                  value={selectedSimBatch}
                  onChange={(e) => setSelectedSimBatch(e.target.value)}
                >
                  <option value="all">All simulations</option>
                  {(() => {
                    const batches = new Map<string, { count: number; date: string }>()
                    savedSims.forEach((s) => {
                      const key = s.batch_id || s.id
                      if (!batches.has(key)) {
                        batches.set(key, { count: 0, date: s.created_at })
                      }
                      batches.get(key)!.count++
                    })
                    return Array.from(batches.entries()).map(([batchKey, info]) => (
                      <option key={batchKey} value={batchKey}>
                        Batch {batchKey.slice(0, 8)}... ({info.count} scenarios) — {new Date(info.date).toLocaleDateString()}
                      </option>
                    ))
                  })()}
                </select>
              </div>
            )}

            {/* Profile link */}
            {selectedUser && (
              <div style={{ marginBottom: '0.75rem' }}>
                <Link to={`/profile/${selectedUser.id}`} className="secondary-btn" style={{ display: 'inline-block', textAlign: 'center', width: '100%' }}>
                  View Full Profile
                </Link>
              </div>
            )}

            {/* Recent Reports */}
            <div className="dashboard-recent">
              <h3>Recent Reports</h3>
              {reports.length === 0 ? (
                <p style={{ color: '#888', fontSize: '0.85rem' }}>No reports yet. <Link to="/analysis">Generate one</Link>.</p>
              ) : (
                <table className="report-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {reports.map((r) => (
                      <tr key={r.id}>
                        <td className="report-id-cell">{r.id.slice(0, 10)}...</td>
                        <td>
                          <span className={`status-pill ${r.status === 'completed' ? 'ok' : r.status === 'failed' ? 'error' : 'running'}`}>
                            {r.status}
                          </span>
                        </td>
                        <td>{formatDate(r.created_at)}</td>
                        <td>
                          <button className="secondary-btn" onClick={() => navigate(`/analysis/${r.id}`)}>View</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Map */}
          <DashboardMap
            properties={properties}
            selectedUser={selectedUser}
            onPropertyClick={(p) => {
              const params = new URLSearchParams({
                property_id: p.id,
                address: p.address,
                price: String(p.asking_price ?? ''),
              })
              navigate(`/negotiate?${params.toString()}`)
            }}
            simulationResults={
              selectedSimBatch === 'all'
                ? savedSims
                : savedSims.filter((s) => (s.batch_id || s.id) === selectedSimBatch)
            }
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
