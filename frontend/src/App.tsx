import { lazy, Suspense, useState, type ReactNode } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import SystemDrawer from './components/SystemDrawer'
import { useAuth } from './hooks/useAuth'
import { usePortfolioMode } from './hooks/usePortfolioMode'

const NegotiationPage = lazy(() => import('./pages/NegotiationPage'))
const UserProfilePage = lazy(() => import('./pages/UserProfilePage'))
const SimulationVisualizePage = lazy(() => import('./pages/SimulationVisualizePage'))
const InvestmentPage = lazy(() => import('./pages/InvestmentPage'))
const SignInPage = lazy(() => import('./pages/SignInPage'))
const OnboardingWizard = lazy(() => import('./pages/OnboardingWizard'))
const HomeGate = lazy(() => import('./components/onboarding/HomeGate'))
const SimulatePage = lazy(() => import('./pages/SimulatePage'))
const SimulateReportPage = lazy(() => import('./pages/SimulateReportPage'))
const SateiPage = lazy(() => import('./pages/SateiPage'))
const NegotiationCoachPage = lazy(() => import('./pages/NegotiationCoachPage'))
const BuyerSimPage = lazy(() => import('./pages/BuyerSimPage'))

function RouteFallback() {
  return <div className="route-loading">Loading…</div>
}

interface RequireAuthProps {
  children: ReactNode
}

function RequireAuth({ children }: RequireAuthProps) {
  const { session, loading } = useAuth()
  const location = useLocation()
  if (loading) return <RouteFallback />
  if (!session) {
    return <Navigate to="/signin" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}

function AuthStatus() {
  const { user, signOut, loading } = useAuth()
  if (loading) return null
  if (!user) {
    return (
      <NavLink to="/signin" className="auth-link">
        Sign in
      </NavLink>
    )
  }
  return (
    <span className="auth-status">
      <span className="auth-email">{user.email}</span>
      <button
        type="button"
        onClick={() => void signOut()}
        className="auth-signout"
      >
        Sign out
      </button>
    </span>
  )
}

function isFullBleedRoute(pathname: string) {
  return (
    pathname === '/' ||
    pathname.startsWith('/invest') ||
    pathname.startsWith('/simulation') ||
    pathname.startsWith('/simulate') ||
    pathname.startsWith('/negotiate') ||
    pathname.startsWith('/onboard')
  )
}

function PortfolioModeToggle() {
  const [mode, setMode] = usePortfolioMode()
  const next = mode === 'individual' ? 'institutional' : 'individual'
  return (
    <button
      type="button"
      className="portfolio-mode-toggle"
      onClick={() => setMode(next)}
      title={`Switch to ${next} mode`}
      data-testid="portfolio-mode-toggle"
    >
      {mode === 'individual' ? 'Individual' : 'Institutional'}
    </button>
  )
}

export default function App() {
  const [systemOpen, setSystemOpen] = useState(false)
  const location = useLocation()
  const mainClassName = isFullBleedRoute(location.pathname)
    ? 'app-main app-main--full'
    : 'app-main app-main--content'

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-inner">
          <div className="app-brand">
            <h1>Real Estate Agentic Platform</h1>
            <p>Investor intelligence, reports, and market replay</p>
          </div>
          <nav className="app-nav">
            <NavLink to="/" end>Dashboard</NavLink>
            <NavLink to="/invest">Investment</NavLink>
            <NavLink to="/profile">Profile</NavLink>
            <PortfolioModeToggle />
            <AuthStatus />
            <button
              className="header-gear-btn"
              onClick={() => setSystemOpen(true)}
              title="System Health"
              type="button"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" />
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
              </svg>
            </button>
          </nav>
        </div>
      </header>
      <main className={mainClassName}>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/signin" element={<SignInPage />} />
            <Route path="/" element={<HomeGate />} />
            <Route path="/onboard" element={<OnboardingWizard />} />
            <Route path="/simulate/:runId" element={<SimulatePage />} />
            <Route path="/simulate/:runId/report" element={<SimulateReportPage />} />
            <Route
              path="/invest"
              element={
                <RequireAuth>
                  <InvestmentPage />
                </RequireAuth>
              }
            />
            {/* Redirects from old routes */}
            <Route path="/analysis/:id?" element={<Navigate to="/invest#analysis" replace />} />
            <Route path="/simulation" element={<Navigate to="/invest#simulation" replace />} />
            <Route path="/portfolio" element={<Navigate to="/invest#portfolio" replace />} />
            <Route path="/simulation/visualize/:propertyId" element={<SimulationVisualizePage />} />
            <Route
              path="/negotiate/:id?"
              element={
                <RequireAuth>
                  <NegotiationPage />
                </RequireAuth>
              }
            />
            <Route path="/satei" element={<SateiPage />} />
            <Route path="/coach" element={<Suspense fallback={<div>Loading...</div>}><NegotiationCoachPage /></Suspense>} />
            <Route path="/buyer-sim" element={<BuyerSimPage />} />
            <Route
              path="/profile/:id?"
              element={
                <RequireAuth>
                  <UserProfilePage />
                </RequireAuth>
              }
            />
          </Routes>
        </Suspense>
      </main>
      <SystemDrawer open={systemOpen} onClose={() => setSystemOpen(false)} />
    </div>
  )
}
