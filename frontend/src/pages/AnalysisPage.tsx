import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../utils/api'
import type { UserProfile } from '../utils/types'
import ReportGenerator from '../components/ReportGenerator'
import ReportList from '../components/ReportList'
import ReportViewer from '../components/ReportViewer'
import SearchDrawer from '../components/SearchDrawer'

const SELECTED_USER_KEY = 'selectedUserId'

export default function AnalysisPage() {
  const { id: reportId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [users, setUsers] = useState<UserProfile[]>([])
  const [selectedUserId, setSelectedUserId] = useState(
    () => localStorage.getItem(SELECTED_USER_KEY) || ''
  )
  const [searchOpen, setSearchOpen] = useState(false)
  const [reportStatus, setReportStatus] = useState<string>('')

  useEffect(() => {
    void loadUsers()
  }, [])

  useEffect(() => {
    if (selectedUserId) {
      localStorage.setItem(SELECTED_USER_KEY, selectedUserId)
    }
  }, [selectedUserId])

  const loadUsers = async () => {
    try {
      const data = await api.users.list()
      setUsers(data)
      if (!selectedUserId && data.length > 0) {
        setSelectedUserId(data[0].id)
      }
    } catch {
      // ignore
    }
  }

  const userOptions = users.map((u) => ({ id: u.id, name: u.name, role: u.role }))

  // No report ID — show generator + list
  if (!reportId) {
    return (
      <div className="analysis-page">
        <div className="page-title-row">
          <h2>Analysis</h2>
          <button className="secondary-btn" onClick={() => setSearchOpen(true)}>
            Property Search
          </button>
        </div>

        <ReportGenerator
          users={users}
          selectedUserId={selectedUserId}
          onUserChange={setSelectedUserId}
        />

        <div style={{ marginTop: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>Reports</h3>
          <ReportList
            users={userOptions}
            selectedUserId={selectedUserId}
            onUserChange={setSelectedUserId}
          />
        </div>

        <SearchDrawer open={searchOpen} onClose={() => setSearchOpen(false)} />
      </div>
    )
  }

  // Report ID — show viewer
  return (
    <div className="analysis-page">
      <div className="page-title-row">
        <Link to="/analysis" className="secondary-btn">All Reports</Link>
        <h2>Intelligence Report</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="secondary-btn" onClick={() => setSearchOpen(true)}>
            Property Search
          </button>
          {reportStatus === 'completed' && (
            <button
              className="primary-btn"
              style={{ background: '#3a3a6e' }}
              onClick={() => navigate('/simulation')}
            >
              Run Simulation with These Insights
            </button>
          )}
        </div>
      </div>

      <ReportViewer
        reportId={reportId}
        onComplete={() => setReportStatus('completed')}
      />

      <SearchDrawer open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  )
}
