import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { UserProfile } from '../../utils/types'
import ReportGenerator from '../ReportGenerator'
import ReportList from '../ReportList'
import ReportViewer from '../ReportViewer'
import SearchDrawer from '../SearchDrawer'

interface AnalysisSectionProps {
  users: UserProfile[]
  selectedUserId: string
  onUserChange: (userId: string) => void
}

export default function AnalysisSection({ users, selectedUserId, onUserChange }: AnalysisSectionProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const reportId = searchParams.get('reportId')
  const [searchOpen, setSearchOpen] = useState(false)

  const userOptions = users.map((u) => ({ id: u.id, name: u.name, role: u.role }))

  const clearReport = () => {
    setSearchParams({})
  }

  if (reportId) {
    return (
      <div className="invest-section" key="analysis-report">
        <div className="invest-section-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 className="invest-section-title">インテリジェンスレポート</h2>
            <p className="invest-section-subtitle">AI生成マーケット分析</p>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <button type="button" className="invest-pill-tab" onClick={clearReport}>
              全レポート
            </button>
            <button type="button" className="invest-pill-tab" onClick={() => setSearchOpen(true)}>
              物件検索
            </button>
          </div>
        </div>
        <ReportViewer reportId={reportId} onComplete={() => {}} />
        <SearchDrawer open={searchOpen} onClose={() => setSearchOpen(false)} />
      </div>
    )
  }

  return (
    <div className="invest-section" key="analysis">
      <div className="invest-section-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 className="invest-section-title">分析</h2>
          <p className="invest-section-subtitle">インテリジェンスレポートの生成・閲覧</p>
        </div>
        <button type="button" className="invest-pill-tab" onClick={() => setSearchOpen(true)}>
          物件検索
        </button>
      </div>

      <div className="invest-card" style={{ marginBottom: 'var(--space-6)' }}>
        <ReportGenerator
          users={users}
          selectedUserId={selectedUserId}
          onUserChange={onUserChange}
        />
      </div>

      <div className="invest-card">
        <div className="invest-card-header">
          <span className="invest-card-title">レポート一覧</span>
        </div>
        <ReportList
          users={userOptions}
          selectedUserId={selectedUserId}
          onUserChange={onUserChange}
        />
      </div>

      <SearchDrawer open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  )
}
