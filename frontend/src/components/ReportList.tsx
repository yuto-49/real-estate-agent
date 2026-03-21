import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../utils/api'

interface ReportStatus {
  id: string
  user_id: string
  status: string
  progress: number
  current_step: string
  step_key?: string
  created_at?: string
}

interface UserOption {
  id: string
  name: string
  role: string
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

interface Props {
  users: UserOption[]
  selectedUserId: string
  onUserChange: (userId: string) => void
}

export default function ReportList({ users, selectedUserId, onUserChange }: Props) {
  const navigate = useNavigate()
  const [reports, setReports] = useState<ReportStatus[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (selectedUserId) {
      void loadReports(selectedUserId)
    }
  }, [selectedUserId])

  const loadReports = async (userId: string) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.reports.listByUser(userId)
      setReports(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reports')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="report-list-controls">
        <div className="agent-control-group">
          <label>User</label>
          <select value={selectedUserId} onChange={(e) => onUserChange(e.target.value)}>
            <option value="">Select a user</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
            ))}
          </select>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading reports...</p>}

      {!loading && selectedUserId && reports.length === 0 && (
        <div className="report-empty">
          <p>No reports found for this user.</p>
        </div>
      )}

      {!loading && reports.length > 0 && (
        <div className="report-list">
          <table className="report-table">
            <thead>
              <tr>
                <th>Report ID</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Created</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id} className={`report-row ${r.status}`}>
                  <td className="report-id-cell">{r.id.slice(0, 12)}...</td>
                  <td>
                    <span className={`status-pill ${r.status === 'completed' ? 'ok' : r.status === 'failed' ? 'error' : 'running'}`}>
                      {r.status}
                    </span>
                  </td>
                  <td>{r.progress}%</td>
                  <td>{formatDate(r.created_at)}</td>
                  <td>
                    <button className="secondary-btn" onClick={() => navigate(`/analysis/${r.id}`)}>
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
