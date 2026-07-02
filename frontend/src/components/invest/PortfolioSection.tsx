import { useState } from 'react'
import HoldingsTab from '../portfolio/HoldingsTab'
import DecisionsTab from '../portfolio/DecisionsTab'

interface PortfolioSectionProps {
  portfolioId: string
}

type SubTab = 'holdings' | 'decisions'

export default function PortfolioSection({ portfolioId }: PortfolioSectionProps) {
  const [subTab, setSubTab] = useState<SubTab>('holdings')

  if (!portfolioId) {
    return (
      <div className="invest-section">
        <div className="invest-empty">
          <div className="invest-empty-title">No Portfolio Selected</div>
          <div className="invest-empty-text">Select or create a portfolio to view holdings and decisions.</div>
        </div>
      </div>
    )
  }

  return (
    <div className="invest-section" key="portfolio">
      <div className="invest-section-header">
        <h2 className="invest-section-title">Portfolio</h2>
        <p className="invest-section-subtitle">Manage holdings and per-holding recommendations</p>
      </div>

      <div className="invest-pill-tabs">
        <button
          type="button"
          className={`invest-pill-tab${subTab === 'holdings' ? ' active' : ''}`}
          onClick={() => setSubTab('holdings')}
        >
          Holdings
        </button>
        <button
          type="button"
          className={`invest-pill-tab${subTab === 'decisions' ? ' active' : ''}`}
          onClick={() => setSubTab('decisions')}
        >
          Decisions
        </button>
      </div>

      {subTab === 'holdings' && <HoldingsTab portfolioId={portfolioId} />}
      {subTab === 'decisions' && <DecisionsTab portfolioId={portfolioId} />}
    </div>
  )
}
