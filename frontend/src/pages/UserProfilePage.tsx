import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api } from '../utils/api'
import {
  formatJaDate,
  formatJpyCompact,
  formatLifeStageLabel,
  formatRiskToleranceLabel,
  formatSearchRadius,
  formatUserRoleLabel,
} from '../utils/japan'
import type { UserProfile } from '../utils/types'
import UserFormModal from '../components/UserFormModal'

const SELECTED_USER_KEY = 'selectedUserId'

function formatBudget(min: number | null | undefined, max: number | null | undefined): string {
  return `${formatJpyCompact(min)} - ${formatJpyCompact(max)}`
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
          setMissingIdMessage('プロフィールがありません。先にダッシュボードから作成してください。')
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
        setMissingIdMessage('プロフィールを選択できませんでした。ダッシュボードから開いてください。')
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

  if (loading) return <div className="profile-page"><p>読み込み中…</p></div>
  if (!id) {
    return (
      <div className="profile-page">
        <p>{missingIdMessage || 'ダッシュボードからプロフィールを選択してください。'} <Link to="/">ダッシュボードへ戻る</Link></p>
      </div>
    )
  }
  if (!user) return <div className="profile-page"><p>プロフィールが見つかりません。<Link to="/">ダッシュボードへ戻る</Link></p></div>

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
            <span className={`status-pill ok`}>{formatUserRoleLabel(user.role)}</span>
            {user.created_at && (
              <p className="profile-member-since">登録日 {formatJaDate(user.created_at)}</p>
            )}
          </div>
        </div>
        <div className="profile-header-actions">
          <button className="primary-btn" onClick={() => setShowModal(true)}>プロフィールを編集</button>
          <Link to="/" className="secondary-btn">ダッシュボードへ戻る</Link>
        </div>
      </div>

      {/* Profile Details */}
      <div className="profile-details-card">
        <h3>プロフィール詳細</h3>
        <div className="user-meta-grid">
          <div><label>予算帯</label><p>{formatBudget(user.budget_min, user.budget_max)}</p></div>
          <div><label>検討期間</label><p>{user.timeline_days ? `${user.timeline_days} 日` : '—'}</p></div>
          <div><label>リスク許容度</label><p>{formatRiskToleranceLabel(user.risk_tolerance)}</p></div>
          <div><label>対象エリア</label><p>{user.zip_code ? `〒${user.zip_code}` : '—'}{user.search_radius ? `（${formatSearchRadius(user.search_radius)}）` : ''}</p></div>
          <div><label>運用フェーズ</label><p>{formatLifeStageLabel(user.life_stage)}</p></div>
          <div><label>希望物件種別</label><p>{user.preferred_types.length ? user.preferred_types.join(', ') : '—'}</p></div>
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
