import { useCallback, useEffect, useState } from 'react'
import { api } from '../../utils/api'
import type { HoldingDecisionResponse, PortfolioHolding } from '../../utils/types'

interface DecisionsTabProps {
  portfolioId: string
}

const ACTION_BLURB: Record<string, string> = {
  HOLD: 'Stay the course — no action recommended.',
  RAISE_RENT: 'Rent has room to move toward market.',
  REFI: 'The note rate is high enough to make refinancing worthwhile.',
  SELL: 'Market conditions favor listing this holding.',
  IMPROVE: 'Invest in the property to protect tenant retention.',
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
        if (active) setError(err instanceof Error ? err.message : 'Failed to load holdings')
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
      setError(err instanceof Error ? err.message : 'Decision lookup failed')
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
          <option value="">Select a holding…</option>
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
          {loading ? 'Evaluating…' : 'Get recommendation'}
        </button>
      </div>

      {decision && (
        <section className="decision-result" data-testid="decision-result">
          <div className="decision-headline">
            <span className="decision-action">{decision.recommendation}</span>
            <span className="decision-score">score {decision.score.toFixed(2)}</span>
          </div>
          <p className="decision-blurb">{ACTION_BLURB[decision.recommendation] ?? ''}</p>
          <p className="decision-rationale">{decision.rationale}</p>
          {!decision.market_context_available && (
            <p className="decision-warning">
              No market signals for this holding — recommendation is driven by financials only.
            </p>
          )}
          <table className="decision-candidates">
            <thead>
              <tr>
                <th>Action</th>
                <th>Score</th>
                <th>Source</th>
                <th>Rationale</th>
              </tr>
            </thead>
            <tbody>
              {decision.candidates.map((cand) => (
                <tr key={`${cand.action}-${cand.source}`}>
                  <td>{cand.action}</td>
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
