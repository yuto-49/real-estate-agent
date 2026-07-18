import { useCallback, useEffect, useState } from 'react'
import { api } from '../../utils/api'
import { formatRecommendationLabel } from '../../utils/japan'
import type { HoldingDecisionResponse, PortfolioHolding } from '../../utils/types'

interface DecisionsTabProps {
  portfolioId: string
}

const ACTION_BLURB: Record<string, string> = {
  HOLD: '現状維持が妥当です。',
  RAISE_RENT: '市場賃料に対して改定余地があります。',
  REFI: '借換による改善効果が見込めます。',
  SELL: '売却を含めた出口戦略の検討余地があります。',
  IMPROVE: '改修や改善投資が有効です。',
}

export default function DecisionsTab({ portfolioId }: DecisionsTabProps) {
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [decision, setDecision] = useState<HoldingDecisionResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    api.portfolio
      .listHoldings(portfolioId)
      .then((h) => {
        if (!active) return
        setHoldings(h)
        if (h.length > 0) setSelectedId(h[0].id)
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : '保有物件を取得できませんでした。')
      })
    return () => {
      active = false
    }
  }, [portfolioId])

  const evaluate = useCallback(async (holdingId: string) => {
    if (!holdingId) return
    setLoading(true)
    try {
      const res = await api.decisions.holding(holdingId)
      setDecision(res)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '推奨アクションを取得できませんでした。')
      setDecision(null)
    } finally {
      setLoading(false)
    }
  }, [])

  return (
    <div className="portfolio-tab" data-testid="decisions-tab">
      {error && <p className="portfolio-error">{error}</p>}

      <div className="decisions-controls">
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          data-testid="decision-holding-select"
        >
          <option value="">保有物件を選択…</option>
          {holdings.map((h) => (
            <option key={h.id} value={h.id}>
              {h.address}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!selectedId || loading}
          onClick={() => void evaluate(selectedId)}
          data-testid="run-decision"
        >
          {loading ? '評価中…' : '推奨アクションを取得'}
        </button>
      </div>

      {decision && (
        <section className="decision-result" data-testid="decision-result">
          <div className="decision-headline">
            <span className="decision-action">{formatRecommendationLabel(decision.recommendation)}</span>
            <span className="decision-score">スコア {decision.score.toFixed(2)}</span>
          </div>
          <p className="decision-blurb">{ACTION_BLURB[decision.recommendation] ?? ''}</p>
          <p className="decision-rationale">{decision.rationale}</p>
          {!decision.market_context_available && (
            <p className="decision-warning">
              市場シグナルがないため、財務情報を中心に判定しています。
            </p>
          )}
          <table className="decision-candidates">
            <thead>
              <tr>
                <th>候補アクション</th>
                <th>スコア</th>
                <th>根拠ソース</th>
                <th>理由</th>
              </tr>
            </thead>
            <tbody>
              {decision.candidates.map((cand) => (
                <tr key={`${cand.action}-${cand.source}`}>
                  <td>{formatRecommendationLabel(cand.action)}</td>
                  <td>{cand.score.toFixed(2)}</td>
                  <td>{cand.source}</td>
                  <td>{cand.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
