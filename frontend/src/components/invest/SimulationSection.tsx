import { useState } from 'react'
import MarketSimulationWorkspace from '../MarketSimulationWorkspace'
import SimulationTab from '../portfolio/SimulationTab'

interface SimulationSectionProps {
  portfolioId: string
}

type SubTab = 'market' | 'property'

export default function SimulationSection({ portfolioId }: SimulationSectionProps) {
  const [subTab, setSubTab] = useState<SubTab>('market')

  return (
    <div className="invest-section" key="simulation">
      <div className="invest-section-header">
        <h2 className="invest-section-title">シミュレーション</h2>
        <p className="invest-section-subtitle">マーケットリプレイと物件別プロジェクション</p>
      </div>

      <div className="invest-pill-tabs">
        <button
          type="button"
          className={`invest-pill-tab${subTab === 'market' ? ' active' : ''}`}
          onClick={() => setSubTab('market')}
        >
          マーケットリプレイ
        </button>
        <button
          type="button"
          className={`invest-pill-tab${subTab === 'property' ? ' active' : ''}`}
          onClick={() => setSubTab('property')}
          disabled={!portfolioId}
        >
          物件シミュレーション
        </button>
      </div>

      {subTab === 'market' && (
        <div className="invest-simulation-container">
          <MarketSimulationWorkspace />
        </div>
      )}

      {subTab === 'property' && portfolioId && (
        <SimulationTab holdingId="" portfolioId={portfolioId} />
      )}

      {subTab === 'property' && !portfolioId && (
        <div className="invest-empty">
          <div className="invest-empty-title">ポートフォリオ未選択</div>
          <div className="invest-empty-text">物件シミュレーションを実行するにはポートフォリオを選択してください。</div>
        </div>
      )}
    </div>
  )
}
