import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../utils/api'

interface SateiSummary {
  id: string
  address: string | null
  satei_price_yen: number | null
  comp_count: number | null
  created_at: string | null
}

interface UserOption {
  id: string
  name: string
  role: string
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatYen(val: number | null | undefined): string {
  if (val == null) return '-'
  return '¥' + val.toLocaleString()
}

interface Props {
  users: UserOption[]
  selectedUserId: string
  onUserChange: (userId: string) => void
}

export default function ReportList({ users, selectedUserId, onUserChange }: Props) {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<SateiSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (selectedUserId) {
      void loadSessions(selectedUserId)
    }
  }, [selectedUserId])

  const loadSessions = async (userId: string) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.satei.listByUser(userId)
      setSessions(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '査定履歴の取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="report-list-controls">
        <div className="agent-control-group">
          <label>ユーザー</label>
          <select value={selectedUserId} onChange={(e) => onUserChange(e.target.value)}>
            <option value="">選択してください</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
            ))}
          </select>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p>読み込み中...</p>}

      {!loading && selectedUserId && sessions.length === 0 && (
        <div className="report-empty">
          <p>査定履歴がありません。</p>
        </div>
      )}

      {!loading && sessions.length > 0 && (
        <div className="report-list">
          <table className="report-table">
            <thead>
              <tr>
                <th>住所</th>
                <th>査定価格</th>
                <th>事例数</th>
                <th>実施日</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td>{s.address || s.id.slice(0, 12) + '...'}</td>
                  <td>{formatYen(s.satei_price_yen)}</td>
                  <td>{s.comp_count ?? '-'}</td>
                  <td>{formatDate(s.created_at)}</td>
                  <td>
                    <button className="secondary-btn" onClick={() => navigate(`/analysis/${s.id}`)}>
                      詳細
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
