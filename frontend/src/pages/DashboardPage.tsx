import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../utils/api'
import type { PortfolioHolding, Property, UserProfile } from '../utils/types'
import UserProfileCard from '../components/UserProfileCard'
import DashboardMap from '../components/DashboardMap'
import UserFormModal from '../components/UserFormModal'
import { formatAssetClassLabel, formatJpyCompact } from '../utils/japan'

const SELECTED_USER_KEY = 'selectedUserId'

function hasHoldingCoordinates(holding: PortfolioHolding): boolean {
  return (
    Number.isFinite(holding.latitude) &&
    Number.isFinite(holding.longitude) &&
    Math.abs(Number(holding.latitude)) <= 90 &&
    Math.abs(Number(holding.longitude)) <= 180
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [users, setUsers] = useState<UserProfile[]>([])
  const [selectedUserId, setSelectedUserId] = useState(
    () => localStorage.getItem(SELECTED_USER_KEY) || ''
  )
  const [loading, setLoading] = useState(true)
  const [properties, setProperties] = useState<Property[]>([])
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([])

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

  useEffect(() => {
    let cancelled = false

    async function loadHoldings() {
      if (!selectedUserId) {
        if (!cancelled) setHoldings([])
        return
      }

      try {
        const portfolios = await api.portfolio.list(selectedUserId)
        if (portfolios.length === 0) {
          if (!cancelled) setHoldings([])
          return
        }
        const perPortfolio = await Promise.all(
          portfolios.map(async (portfolio) => {
            try {
              return await api.portfolio.listHoldings(portfolio.id)
            } catch {
              return []
            }
          }),
        )
        if (!cancelled) {
          setHoldings(perPortfolio.flat())
        }
      } catch {
        if (!cancelled) {
          setHoldings([])
        }
      }
    }

    void loadHoldings()

    return () => {
      cancelled = true
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
  const mappedHoldings = holdings.filter(hasHoldingCoordinates)

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
    if (!window.confirm(`「${selectedUser.name}」を削除しますか？この操作は元に戻せません。`)) return
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
        <h2>投資ダッシュボード</h2>
      </div>

      {loading && <p>読み込み中…</p>}

      {!loading && (
        <div className="dashboard-map-layout">
          {/* Sidebar */}
          <div className="dashboard-sidebar">
            <div className="agent-control-group">
              <label>現在の投資家プロフィール</label>
              <div className="user-selector-row">
                <select value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value)}>
                  <option value="">プロフィールを選択</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
                  ))}
                </select>
                <button className="primary-btn compact-btn" onClick={openCreate}>+ 新規</button>
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
                <p>プロフィールがまだありません。</p>
                <button className="primary-btn" onClick={openCreate}>最初のプロフィールを作成</button>
              </div>
            )}

            {/* Quick Actions */}
            <section className="dashboard-recent" data-testid="dashboard-holdings">
              <h3>現在の保有物件所在地</h3>
              {!selectedUser ? (
                <p className="dashboard-muted-copy">
                  投資家プロフィールを選択すると、保有物件の所在地を地図と一覧で確認できます。
                </p>
              ) : holdings.length === 0 ? (
                <p className="dashboard-muted-copy">
                  まだ保有物件が登録されていません。ポートフォリオから追加すると、この地図に反映されます。
                </p>
              ) : (
                <>
                  <p className="dashboard-muted-copy">
                    {holdings.length} 件中 {mappedHoldings.length} 件を地図表示できます。
                  </p>
                  <ul className="dashboard-holdings-list">
                    {holdings.slice(0, 6).map((holding) => (
                      <li key={holding.id} data-testid="dashboard-holding-row">
                        <strong>{holding.address}</strong>
                        <div className="dashboard-holdings-meta">
                          <span>{formatAssetClassLabel(holding.asset_class)}</span>
                          <span>{holding.zip_code ? `〒${holding.zip_code}` : '郵便番号未設定'}</span>
                          <span>
                            {hasHoldingCoordinates(holding)
                              ? 'マップ連携済み'
                              : '地図座標未設定'}
                          </span>
                          {holding.financials?.monthly_rent != null && (
                            <span>月額賃料 {formatJpyCompact(holding.financials.monthly_rent)}</span>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>

            <div className="dashboard-quick-actions">
              <h3>クイック操作</h3>
              <div className="dashboard-action-buttons">
                <button className="primary-btn" onClick={() => navigate('/portfolio')}>
                  ポートフォリオを開く
                </button>
              </div>
            </div>

            {/* Profile link */}
            {selectedUser && (
              <div className="dashboard-link-stack">
                <Link to={`/profile/${selectedUser.id}`} className="secondary-btn dashboard-link-btn">
                  プロフィール詳細を見る
                </Link>
              </div>
            )}
          </div>

          {/* Map */}
          <DashboardMap
            properties={properties}
            holdings={holdings}
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
