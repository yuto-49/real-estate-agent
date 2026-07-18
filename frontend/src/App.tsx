import { lazy, Suspense, useState, type ReactNode } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import SystemDrawer from './components/SystemDrawer'
import { useAuth } from './hooks/useAuth'

const UserProfilePage = lazy(() => import('./pages/UserProfilePage'))
const PortfolioPage = lazy(() => import('./pages/PortfolioPage'))
const SignInPage = lazy(() => import('./pages/SignInPage'))
const OnboardingWizard = lazy(() => import('./pages/OnboardingWizard'))
const HomeGate = lazy(() => import('./components/onboarding/HomeGate'))
const SimulatePage = lazy(() => import('./pages/SimulatePage'))
const SimulateReportPage = lazy(() => import('./pages/SimulateReportPage'))

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
        ログイン
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
        ログアウト
      </button>
    </span>
  )
}

function isFullBleedRoute(pathname: string) {
  return (
    pathname === '/' ||
    pathname.startsWith('/simulate') ||
    pathname.startsWith('/onboard')
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
            <h1>日本不動産エージェント</h1>
            <p>日本の収益不動産向けポートフォリオ分析</p>
          </div>
          <nav className="app-nav">
            <NavLink to="/" end>ダッシュボード</NavLink>
            <NavLink to="/portfolio">ポートフォリオ</NavLink>
            <NavLink to="/profile">プロフィール</NavLink>
            <AuthStatus />
            <button
              className="header-gear-btn"
              onClick={() => setSystemOpen(true)}
              title="システム状態"
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
              path="/portfolio"
              element={
                <RequireAuth>
                  <PortfolioPage />
                </RequireAuth>
              }
            />
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
