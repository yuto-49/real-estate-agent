import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../utils/api'
import type { InvestorPortfolio, UserProfile } from '../utils/types'
import InvestSidebar from '../components/invest/InvestSidebar'
import type { InvestSection } from '../components/invest/InvestSidebar'
import InvestContextBar from '../components/invest/InvestContextBar'

const DashboardSection = lazy(() => import('../components/invest/DashboardSection'))
const PortfolioSection = lazy(() => import('../components/invest/PortfolioSection'))
const AnalysisSection = lazy(() => import('../components/invest/AnalysisSection'))
const SimulationSection = lazy(() => import('../components/invest/SimulationSection'))
const StrategySection = lazy(() => import('../components/invest/StrategySection'))

const SELECTED_USER_KEY = 'selectedUserId'

function hashToSection(hash: string): InvestSection {
  const map: Record<string, InvestSection> = {
    '#dashboard': 'dashboard',
    '#portfolio': 'portfolio',
    '#analysis': 'analysis',
    '#simulation': 'simulation',
    '#strategy': 'strategy',
  }
  return map[hash] ?? 'dashboard'
}

export default function InvestmentPage() {
  const location = useLocation()
  const [activeSection, setActiveSection] = useState<InvestSection>(
    () => hashToSection(location.hash),
  )

  const [users, setUsers] = useState<UserProfile[]>([])
  const [selectedUserId, setSelectedUserId] = useState(
    () => localStorage.getItem(SELECTED_USER_KEY) || '',
  )
  const [portfolios, setPortfolios] = useState<InvestorPortfolio[]>([])
  const [selectedPortfolioId, setSelectedPortfolioId] = useState('')
  const [newPortfolioName, setNewPortfolioName] = useState('')
  const [error, setError] = useState('')

  // Sync hash to section
  useEffect(() => {
    const section = hashToSection(location.hash)
    setActiveSection(section)
  }, [location.hash])

  // Update hash when section changes
  const handleSectionChange = useCallback((section: InvestSection) => {
    setActiveSection(section)
    window.history.replaceState(null, '', `#${section}`)
  }, [])

  // Load users
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

  // Persist selected user
  useEffect(() => {
    if (selectedUserId) localStorage.setItem(SELECTED_USER_KEY, selectedUserId)
  }, [selectedUserId])

  // Load portfolios
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
    <div className="invest-layout" data-testid="investment-page">
      <InvestSidebar active={activeSection} onChange={handleSectionChange} />

      <InvestContextBar
        users={users}
        selectedUserId={selectedUserId}
        onUserChange={setSelectedUserId}
        portfolios={portfolios}
        selectedPortfolioId={selectedPortfolioId}
        onPortfolioChange={setSelectedPortfolioId}
        newPortfolioName={newPortfolioName}
        onNewPortfolioNameChange={setNewPortfolioName}
        onCreatePortfolio={() => void createPortfolio()}
      />

      <div className="invest-content">
        {error && <p className="invest-error">{error}</p>}

        <Suspense fallback={<div className="invest-empty">読み込み中...</div>}>
          {activeSection === 'dashboard' && (
            <DashboardSection
              portfolioId={selectedPortfolioId}
              userId={selectedUserId}
            />
          )}
          {activeSection === 'portfolio' && (
            <PortfolioSection portfolioId={selectedPortfolioId} />
          )}
          {activeSection === 'analysis' && (
            <AnalysisSection users={users} selectedUserId={selectedUserId} onUserChange={setSelectedUserId} />
          )}
          {activeSection === 'simulation' && (
            <SimulationSection portfolioId={selectedPortfolioId} />
          )}
          {activeSection === 'strategy' && (
            <StrategySection portfolioId={selectedPortfolioId} />
          )}
        </Suspense>
      </div>
    </div>
  )
}
