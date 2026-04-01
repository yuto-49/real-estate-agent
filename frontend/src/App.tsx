import { useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'
import AnalysisPage from './pages/AnalysisPage'
import SimulationPage from './pages/SimulationPage'
import NegotiationPage from './pages/NegotiationPage'
import UserProfilePage from './pages/UserProfilePage'
import SimulationVisualizePage from './pages/SimulationVisualizePage'
import SystemDrawer from './components/SystemDrawer'

export default function App() {
  const [systemOpen, setSystemOpen] = useState(false)

  return (
    <div className="app">
      <header className="app-header">
        <h1>Real Estate Agentic Platform</h1>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/analysis">Analysis</NavLink>
          <NavLink to="/simulation">Simulation</NavLink>
          <NavLink to="/profile">Profile</NavLink>
          <button
            className="header-gear-btn"
            onClick={() => setSystemOpen(true)}
            title="System Health"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
          </button>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/analysis/:id?" element={<AnalysisPage />} />
          <Route path="/simulation" element={<SimulationPage />} />
          <Route path="/simulation/visualize/:propertyId" element={<SimulationVisualizePage />} />
          <Route path="/negotiate/:id?" element={<NegotiationPage />} />
          <Route path="/profile/:id?" element={<UserProfilePage />} />
        </Routes>
      </main>
      <SystemDrawer open={systemOpen} onClose={() => setSystemOpen(false)} />
    </div>
  )
}
