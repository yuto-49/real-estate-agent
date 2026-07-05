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
          <div className="invest-empty-title">ポートフォリオ未選択</div>
          <div className="invest-empty-text">保有物件と判断を表示するにはポートフォリオを選択してください。</div>
        </div>
      </div>
    )
  }

  return (
    <div className="invest-section" key="portfolio">
      <div className="invest-section-header">
        <h2 className="invest-section-title">ポートフォリオ</h2>
        <p className="invest-section-subtitle">保有物件と物件別レコメンデーションの管理</p>
      </div>

      <div className="invest-pill-tabs">
        <button
          type="button"
          className={`invest-pill-tab${subTab === 'holdings' ? ' active' : ''}`}
          onClick={() => setSubTab('holdings')}
        >
          保有物件
        </button>
        <button
          type="button"
          className={`invest-pill-tab${subTab === 'decisions' ? ' active' : ''}`}
          onClick={() => setSubTab('decisions')}
        >
          判断履歴
        </button>
      </div>

      {subTab === 'holdings' && <HoldingsTab portfolioId={portfolioId} />}
      {subTab === 'decisions' && <DecisionsTab portfolioId={portfolioId} />}
    </div>
  )
}
