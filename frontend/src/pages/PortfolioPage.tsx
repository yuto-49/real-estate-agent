import { useCallback, useEffect, useState } from 'react'
import { api } from '../utils/api'
import type { InvestorPortfolio, UserProfile } from '../utils/types'
import { usePortfolioMode } from '../hooks/usePortfolioMode'
import HoldingsTab from '../components/portfolio/HoldingsTab'
import UnderwriteTab from '../components/portfolio/UnderwriteTab'
import StressTestTab from '../components/portfolio/StressTestTab'
import DecisionsTab from '../components/portfolio/DecisionsTab'
import OverviewTab from '../components/portfolio/OverviewTab'
import RecentSimulations from '../components/portfolio/RecentSimulations'
import StrategyTab from '../components/portfolio/StrategyTab'

const SELECTED_USER_KEY = 'selectedUserId'

type TabKey =
  | 'overview'
  | 'holdings'
  | 'underwrite'
  | 'stress'
  | 'decisions'
  | 'strategy'

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'holdings', label: 'Holdings' },
  { key: 'underwrite', label: 'Underwrite' },
  { key: 'stress', label: 'Stress Test' },
  { key: 'decisions', label: 'Decisions' },
  { key: 'strategy', label: 'Strategy' },
]

export default function PortfolioPage() {
  const [mode] = usePortfolioMode()
  const [users, setUsers] = useState<UserProfile[]>([])
  const [selectedUserId, setSelectedUserId] = useState(
    () => localStorage.getItem(SELECTED_USER_KEY) || '',
  )
  const [portfolios, setPortfolios] = useState<InvestorPortfolio[]>([])
  const [selectedPortfolioId, setSelectedPortfolioId] = useState('')
  const [newPortfolioName, setNewPortfolioName] = useState('')
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [error, setError] = useState('')

  useEffect(() => {
    api.users
      .list()
      .then((data) => {
        setUsers(data)
        if (!selectedUserId && data.length > 0) setSelectedUserId(data[0].id)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load users'))
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
      setError(err instanceof Error ? err.message : 'Failed to load portfolios')
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
      setError(err instanceof Error ? err.message : 'Failed to create portfolio')
    }
  }

  return (
    <div className="portfolio-page" data-testid="portfolio-page">
      <header className="portfolio-page-header">
        <div>
          <h2>Investor Portfolio</h2>
          <p>
            Track holdings, underwrite deals, stress-test cash flow, and get
            per-holding recommendations.{' '}
            <span className="portfolio-mode-badge" data-testid="portfolio-mode-badge">
              {mode === 'individual' ? 'Individual investor mode' : 'Institutional mode'}
            </span>
          </p>
        </div>
      </header>

      {error && <p className="portfolio-error">{error}</p>}

      <section className="portfolio-selectors">
        <label>
          Investor
          <select
            value={selectedUserId}
            onChange={(e) => setSelectedUserId(e.target.value)}
            data-testid="portfolio-user-select"
          >
            <option value="">Select investor…</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Portfolio
          <select
            value={selectedPortfolioId}
            onChange={(e) => setSelectedPortfolioId(e.target.value)}
            data-testid="portfolio-select"
          >
            <option value="">Select portfolio…</option>
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        <div className="portfolio-create">
          <input
            placeholder="New portfolio name"
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
            Create
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
        {(activeTab === 'overview' ||
          activeTab === 'holdings' ||
          activeTab === 'decisions' ||
          activeTab === 'strategy') &&
          (selectedPortfolioId ? (
            activeTab === 'overview' ? (
              <>
                <OverviewTab portfolioId={selectedPortfolioId} />
                <RecentSimulations />
              </>
            ) : activeTab === 'holdings' ? (
              <HoldingsTab portfolioId={selectedPortfolioId} />
            ) : activeTab === 'decisions' ? (
              <DecisionsTab portfolioId={selectedPortfolioId} />
            ) : (
              <StrategyTab portfolioId={selectedPortfolioId} />
            )
          ) : (
            <p className="portfolio-empty">
              Select or create a portfolio to see the summary, holdings,
              recommendations, and strategy run.
            </p>
          ))}
      </div>
    </div>
  )
}
