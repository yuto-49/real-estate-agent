import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { api } from '../../utils/api'

const DashboardPage = lazy(() => import('../../pages/DashboardPage'))

function Loading(): ReactNode {
  return <div className="route-loading">Loading…</div>
}

/**
 * Router gate sitting at `/`. When the user is signed in and has no
 * portfolio yet, redirects to `/onboard`. Otherwise renders the legacy
 * DashboardPage so we don't disrupt existing users in P1.
 */
export default function HomeGate(): ReactNode {
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [gateResolved, setGateResolved] = useState(false)

  useEffect(() => {
    if (authLoading) return
    let cancelled = false
    const userId = user?.id

    async function decide() {
      if (!userId) {
        if (!cancelled) setGateResolved(true)
        return
      }
      try {
        const state = await api.onboarding.state(userId)
        if (cancelled) return
        if (!state.has_portfolio) {
          navigate('/onboard', { replace: true })
          return
        }
      } catch {
        // network / API error — fall back to dashboard
      }
      if (!cancelled) setGateResolved(true)
    }

    void decide()
    return () => {
      cancelled = true
    }
  }, [authLoading, user?.id, navigate])

  if (authLoading || !gateResolved) return <Loading />
  return (
    <Suspense fallback={<Loading />}>
      <DashboardPage />
    </Suspense>
  )
}
