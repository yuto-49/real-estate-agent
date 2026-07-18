import { useCallback, useEffect, useState } from 'react'
import { api } from '../utils/api'
import type { InvestorPortfolio, UserProfile } from '../utils/types'
import HoldingsTab from '../components/portfolio/HoldingsTab'
import UnderwriteTab from '../components/portfolio/UnderwriteTab'
import StressTestTab from '../components/portfolio/StressTestTab'
import DecisionsTab from '../components/portfolio/DecisionsTab'
import AnalysisTab from '../components/portfolio/AnalysisTab'
import RecentSimulations from '../components/portfolio/RecentSimulations'
import SimulationTab from '../components/portfolio/SimulationTab'

const SELECTED_USER_KEY = 'selectedUserId'

type TabKey =
  | 'analysis'
  | 'holdings'
  | 'underwrite'
  | 'stress'
  | 'decisions'
  | 'simulation'

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'analysis', label: '概要' },
  { key: 'holdings', label: '保有物件' },
  { key: 'underwrite', label: '収支試算' },
  { key: 'stress', label: 'ストレステスト' },
  { key: 'decisions', label: '推奨アクション' },
  { key: 'simulation', label: '将来シミュレーション' },
]

export default function PortfolioPage() {
  const [users, setUsers] = useState<UserProfile[]>([])
  const [selectedUserId, setSelectedUserId] = useState(
    () => localStorage.getItem(SELECTED_USER_KEY) || '',
  )
  const [portfolios, setPortfolios] = useState<InvestorPortfolio[]>([])
  const [selectedPortfolioId, setSelectedPortfolioId] = useState('')
  const [newPortfolioName, setNewPortfolioName] = useState('')
  const [activeTab, setActiveTab] = useState<TabKey>('analysis')
  const [error, setError] = useState('')

  useEffect(() => {
    api.users
      .list()
      .then((data) => {
        setUsers(data)
        if (!selectedUserId && data.length > 0) setSelectedUserId(data[0].id)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'プロフィール一覧を取得できませんでした。'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (selectedUserId) localStorage.setItem(SELECTED_USER_KEY, selectedUserId)
  }, [selectedUserId])

  const loadPortfolios = useCallback(async () => {
    if (!selectedUserId) return
    try {
      const data = await api.portfolio.list(selectedUserId)
      setPortfolios(data)
      setSelectedPortfolioId((prev) =>
        prev && data.some((p) => p.id === prev) ? prev : data[0]?.id ?? '',
      )
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ポートフォリオ一覧を取得できませんでした。')
    }
  }, [selectedUserId])

  useEffect(() => {
    void loadPortfolios()
  }, [loadPortfolios])

  const createPortfolio = async () => {
    if (!selectedUserId || !newPortfolioName.trim()) return
    try {
      const created = await api.portfolio.create({
        user_id: selectedUserId,
        name: newPortfolioName.trim(),
      })
      setNewPortfolioName('')
      await loadPortfolios()
      setSelectedPortfolioId(created.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ポートフォリオを作成できませんでした。')
    }
  }

  return (
    <div className="portfolio-page" data-testid="portfolio-page">
      <header className="portfolio-page-header">
        <div>
          <h2>日本不動産ポートフォリオ</h2>
          <p>
            保有物件の管理、収支試算、ストレステスト、推奨アクションを日本市場向けに確認できます。
          </p>
        </div>
      </header>

      {error && <p className="portfolio-error">{error}</p>}

      <section className="portfolio-selectors">
        <label>
          投資家
          <select
            value={selectedUserId}
            onChange={(e) => setSelectedUserId(e.target.value)}
            data-testid="portfolio-user-select"
          >
            <option value="">投資家を選択…</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          ポートフォリオ
          <select
            value={selectedPortfolioId}
            onChange={(e) => setSelectedPortfolioId(e.target.value)}
            data-testid="portfolio-select"
          >
            <option value="">ポートフォリオを選択…</option>
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        <div className="portfolio-create">
          <input
            placeholder="新しいポートフォリオ名"
            value={newPortfolioName}
            onChange={(e) => setNewPortfolioName(e.target.value)}
            data-testid="new-portfolio-name"
          />
          <button
            type="button"
            onClick={() => void createPortfolio()}
            disabled={!selectedUserId || !newPortfolioName.trim()}
            data-testid="create-portfolio-btn"
          >
            作成
          </button>
        </div>
      </section>

      <nav className="portfolio-tabs" data-testid="portfolio-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={activeTab === tab.key ? 'portfolio-tab-btn active' : 'portfolio-tab-btn'}
            onClick={() => setActiveTab(tab.key)}
            data-testid={`tab-${tab.key}`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="portfolio-tab-body">
        {activeTab === 'underwrite' && <UnderwriteTab />}
        {activeTab === 'stress' && <StressTestTab />}
        {(activeTab === 'analysis' ||
          activeTab === 'holdings' ||
          activeTab === 'decisions' ||
          activeTab === 'simulation') &&
          (selectedPortfolioId ? (
            activeTab === 'analysis' ? (
              <>
                <AnalysisTab portfolioId={selectedPortfolioId} />
                <RecentSimulations />
              </>
            ) : activeTab === 'holdings' ? (
              <HoldingsTab portfolioId={selectedPortfolioId} />
            ) : activeTab === 'decisions' ? (
              <DecisionsTab portfolioId={selectedPortfolioId} />
            ) : (
              <SimulationTab portfolioId={selectedPortfolioId} />
            )
          ) : (
            <p className="portfolio-empty">
              ポートフォリオを選択または作成すると、保有物件、分析、推奨アクション、将来シミュレーションを確認できます。
            </p>
          ))}
      </div>
    </div>
  )
}
