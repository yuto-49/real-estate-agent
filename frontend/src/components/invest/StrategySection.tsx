import { useState } from 'react'
import UnderwriteTab from '../portfolio/UnderwriteTab'
import StressTestTab from '../portfolio/StressTestTab'
import StrategyTab from '../portfolio/StrategyTab'

interface StrategySectionProps {
  portfolioId: string
}

type SubTab = 'underwrite' | 'stress' | 'strategy'

export default function StrategySection({ portfolioId }: StrategySectionProps) {
  const [subTab, setSubTab] = useState<SubTab>('underwrite')

  return (
    <div className="invest-section" key="strategy">
      <div className="invest-section-header">
        <h2 className="invest-section-title">戦略分析</h2>
        <p className="invest-section-subtitle">収支シミュレーション、ストレステスト、ポートフォリオ戦略分析</p>
      </div>

      <div className="invest-pill-tabs">
        <button
          type="button"
          className={`invest-pill-tab${subTab === 'underwrite' ? ' active' : ''}`}
          onClick={() => setSubTab('underwrite')}
        >
          収支分析
        </button>
        <button
          type="button"
          className={`invest-pill-tab${subTab === 'stress' ? ' active' : ''}`}
          onClick={() => setSubTab('stress')}
        >
          ストレステスト
        </button>
        <button
          type="button"
          className={`invest-pill-tab${subTab === 'strategy' ? ' active' : ''}`}
          onClick={() => setSubTab('strategy')}
          disabled={!portfolioId}
        >
          戦略実行
        </button>
      </div>

      {subTab === 'underwrite' && <UnderwriteTab />}
      {subTab === 'stress' && <StressTestTab />}
      {subTab === 'strategy' && portfolioId && <StrategyTab portfolioId={portfolioId} />}
      {subTab === 'strategy' && !portfolioId && (
        <div className="invest-empty">
          <div className="invest-empty-title">ポートフォリオ未選択</div>
          <div className="invest-empty-text">戦略分析を実行するにはポートフォリオを選択してください。</div>
        </div>
      )}
    </div>
  )
}
