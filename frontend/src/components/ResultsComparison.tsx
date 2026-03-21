import { useNavigate } from 'react-router-dom'
import PriceChart from './PriceChart'
import type { BatchSimulationResult } from '../utils/types'

interface Props {
  result: BatchSimulationResult
  propertyId: string
  askingPrice: number
}

export default function ResultsComparison({ result, propertyId, askingPrice }: Props) {
  const navigate = useNavigate()
  const outcomes = result.outcomes ?? []
  const comparison = result.comparison ?? { win_rate: 0, deals_reached: 0, total_scenarios: 0, average_deal_price: null, best_scenario: null, best_price: null }

  const scenarioPaths = outcomes
    .filter((o) => o.price_path && o.price_path.length > 0)
    .map((o) => ({
      scenario: o.scenario,
      price_path: o.price_path,
    }))

  return (
    <div className="results-comparison">
      {/* Win Rate Bar */}
      <div className="win-rate-bar">
        <div className="win-rate-header">
          <span>Deal Success Rate</span>
          <span className="win-rate-value">{comparison.win_rate}%</span>
        </div>
        <div className="workflow-progress-bar" style={{ height: '16px' }}>
          <div
            className="workflow-progress-fill complete"
            style={{ width: `${comparison.win_rate}%` }}
          />
        </div>
        <span style={{ fontSize: '0.78rem', color: '#888' }}>
          {comparison.deals_reached} of {comparison.total_scenarios} scenarios reached a deal
        </span>
      </div>

      {/* Recommendation */}
      {comparison.best_scenario && (
        <div className="recommendation-card">
          <h4>Recommended Strategy</h4>
          <p>
            <strong>{comparison.best_scenario.replace(/_/g, ' ')}</strong> achieved the best price
            at <strong>${comparison.best_price?.toLocaleString()}</strong>.
          </p>
          {comparison.average_deal_price && (
            <p style={{ fontSize: '0.85rem', color: '#666' }}>
              Average deal price across successful scenarios: ${comparison.average_deal_price.toLocaleString()}
            </p>
          )}
        </div>
      )}

      {/* Outcome Table */}
      <div className="outcome-table-wrap">
        <h4>Scenario Outcomes</h4>
        <table className="report-table">
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Outcome</th>
              <th>Final Price</th>
              <th>Rounds</th>
              <th>Final Spread</th>
            </tr>
          </thead>
          <tbody>
            {outcomes.map((o) => (
              <tr key={o.scenario}>
                <td style={{ textTransform: 'capitalize' }}>{o.scenario.replace(/_/g, ' ')}</td>
                <td>
                  <span className={`status-pill ${o.outcome === 'accepted' ? 'ok' : o.outcome === 'rejected' ? 'error' : 'running'}`}>
                    {o.outcome}
                  </span>
                </td>
                <td>{o.final_price ? `$${o.final_price.toLocaleString()}` : 'N/A'}</td>
                <td>{o.rounds_completed}</td>
                <td>${o.final_spread.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Price Chart */}
      {scenarioPaths.length > 0 && (
        <PriceChart scenarioPaths={scenarioPaths} askingPrice={askingPrice} />
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
        <button
          className="primary-btn"
          onClick={() => {
            const params = new URLSearchParams({
              property_id: propertyId,
              price: String(comparison.best_price ?? askingPrice),
            })
            navigate(`/negotiate?${params.toString()}`)
          }}
        >
          Start Real Negotiation
        </button>
      </div>
    </div>
  )
}
