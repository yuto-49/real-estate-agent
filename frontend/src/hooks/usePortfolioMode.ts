import { useCallback, useEffect, useState } from 'react'
import type { PortfolioMode } from '../utils/types'

/**
 * Top-nav mode toggle (Phase P6). The platform serves both institutional and
 * individual investors; this flag is the manual switch between the two
 * surfaces. Persisted to localStorage and broadcast so the nav and any open
 * page stay in sync within the tab.
 */
const MODE_KEY = 'portfolioMode'
const MODE_EVENT = 'portfolio-mode-change'

export function getPortfolioMode(): PortfolioMode {
  return localStorage.getItem(MODE_KEY) === 'individual'
    ? 'individual'
    : 'institutional'
}

export function usePortfolioMode(): [PortfolioMode, (mode: PortfolioMode) => void] {
  const [mode, setModeState] = useState<PortfolioMode>(getPortfolioMode)

  useEffect(() => {
    const sync = () => setModeState(getPortfolioMode())
    window.addEventListener(MODE_EVENT, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(MODE_EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  const setMode = useCallback((next: PortfolioMode) => {
    localStorage.setItem(MODE_KEY, next)
    window.dispatchEvent(new Event(MODE_EVENT))
  }, [])

  return [mode, setMode]
}
