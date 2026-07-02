import { useCallback, useEffect, useState } from 'react'
import { api } from '../../utils/api'
import type { PortfolioHolding } from '../../utils/types'
import ShockConfigurator from '../simulation/ShockConfigurator'
import type { ShockEntry } from '../simulation/ShockConfigurator'

interface SimulationTabProps {
  holdingId: string
  portfolioId: string
}

interface SimulationRoundRow {
  round_num: number
  noi: number
  occupancy: number
  dscr: number
  cap_rate: number
  recommendation: string
  shocks: string[]
  churn_avg: number
}

interface SimulationRunResult {
  run_id: string
  status: string
  recommendation: string
  converged: boolean
  converged_at_round: number | null
  final_noi: number
  final_dscr: number
  final_cap_rate: number
  final_occupancy: number
  rounds_count: number
}

interface ReplayResponse {
  run_id: string
  rounds: SimulationRoundRow[]
  converged: boolean
  converged_at_round: number | null
}

const RECOMMENDATION_COLORS: Record<string, string> = {
  HOLD: '#3b82f6',
  SELL: '#ef4444',
  REFI: '#eab308',
  IMPROVE: '#22c55e',
}

const RECOMMENDATION_LABELS: Record<string, string> = {
  HOLD: '保有継続',
  SELL: '売却推奨',
  REFI: '借換検討',
  IMPROVE: '改善投資',
  RAISE_RENT: '家賃改定',
}

export default function SimulationTab({ holdingId, portfolioId }: SimulationTabProps) {
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([])
  const [selectedHoldingId, setSelectedHoldingId] = useState(holdingId)
  const [shocks, setShocks] = useState<ShockEntry[]>([])
  const [maxRounds, setMaxRounds] = useState(20)
  const [convergenceThreshold, setConvergenceThreshold] = useState(0.02)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<SimulationRunResult | null>(null)
  const [rounds, setRounds] = useState<SimulationRoundRow[]>([])

  useEffect(() => {
    let active = true
    api.portfolio
      .listHoldings(portfolioId)
      .then((h) => {
        if (!active) return
        setHoldings(h)
        if (!selectedHoldingId && h.length > 0) setSelectedHoldingId(h[0].id)
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : 'Failed to load holdings')
      })
    return () => {
      active = false
    }
  }, [portfolioId, selectedHoldingId])

  const runSimulation = useCallback(async () => {
    if (!selectedHoldingId) return
    setLoading(true)
    setError('')
    setResult(null)
    setRounds([])
    try {
      const body = {
        holding_id: selectedHoldingId,
        portfolio_id: portfolioId,
        max_rounds: maxRounds,
        shocks: shocks.map((s) => ({
          round_num: s.round_num,
          shock_type: s.shock_type,
          magnitude: s.magnitude,
          label: s.label,
        })),
        convergence_threshold: convergenceThreshold,
      }
      const res = await api.simulation.runUnified(body)
      setResult(res)

      // Fetch replay for round-by-round detail
      try {
        const replay = await api.simulation.replayUnified(res.run_id)
        setRounds(replay.rounds)
      } catch {
        // replay is optional — result is still valid
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed')
    } finally {
      setLoading(false)
    }
  }, [selectedHoldingId, portfolioId, maxRounds, shocks, convergenceThreshold])

  const badgeColor = result ? (RECOMMENDATION_COLORS[result.recommendation] ?? '#6b7280') : '#6b7280'

  return (
    <div className="portfolio-tab" data-testid="simulation-tab">
      {error && <p className="portfolio-error">{error}</p>}

      <div className="simulation-controls">
        <label>
          対象物件
          <select
            value={selectedHoldingId}
            onChange={(e) => setSelectedHoldingId(e.target.value)}
            data-testid="simulation-holding-select"
          >
            <option value="">物件を選択…</option>
            {holdings.map((h) => (
              <option key={h.id} value={h.id}>
                {h.address}
              </option>
            ))}
          </select>
        </label>

        <label>
          最大ラウンド数
          <input
            type="number"
            min={1}
            max={50}
            value={maxRounds}
            onChange={(e) => setMaxRounds(Number(e.target.value))}
            data-testid="simulation-max-rounds"
          />
        </label>

        <label>
          収束閾値
          <input
            type="number"
            min={0}
            max={1}
            step={0.005}
            value={convergenceThreshold}
            onChange={(e) => setConvergenceThreshold(Number(e.target.value))}
            data-testid="simulation-convergence"
          />
        </label>
      </div>

      <ShockConfigurator shocks={shocks} onShocksChange={setShocks} />

      <div className="simulation-actions">
        <button
          type="button"
          disabled={!selectedHoldingId || loading}
          onClick={() => void runSimulation()}
          data-testid="run-simulation"
        >
          {loading ? '実行中…' : 'シミュレーション実行'}
        </button>
      </div>

      {result && (
        <section className="simulation-result" data-testid="simulation-result">
          <div className="simulation-headline">
            <span
              className="simulation-recommendation-badge"
              style={{ backgroundColor: badgeColor, color: '#fff', padding: '4px 12px', borderRadius: '4px' }}
              data-testid="simulation-recommendation"
            >
              {RECOMMENDATION_LABELS[result.recommendation] ?? result.recommendation}
            </span>
            {result.converged && (
              <span className="simulation-converged-badge" data-testid="simulation-converged">
                ラウンド {result.converged_at_round} で収束
              </span>
            )}
          </div>

          <div className="simulation-summary">
            <div>
              <strong>最終NOI（純収益）:</strong> {result.final_noi.toLocaleString()}
            </div>
            <div>
              <strong>最終DSCR:</strong> {result.final_dscr.toFixed(2)}
            </div>
            <div>
              <strong>最終利回り:</strong> {(result.final_cap_rate * 100).toFixed(2)}%
            </div>
            <div>
              <strong>最終稼働率:</strong> {(result.final_occupancy * 100).toFixed(1)}%
            </div>
            <div>
              <strong>実行ラウンド数:</strong> {result.rounds_count}
            </div>
          </div>

          {rounds.length > 0 && (
            <table className="simulation-rounds-table" data-testid="simulation-rounds-table">
              <thead>
                <tr>
                  <th>ラウンド</th>
                  <th>NOI</th>
                  <th>稼働率</th>
                  <th>DSCR</th>
                  <th>利回り</th>
                  <th>判断</th>
                  <th>ショック</th>
                </tr>
              </thead>
              <tbody>
                {rounds.map((r) => (
                  <tr key={r.round_num}>
                    <td>{r.round_num}</td>
                    <td>{r.noi.toLocaleString()}</td>
                    <td>{(r.occupancy * 100).toFixed(1)}%</td>
                    <td>{r.dscr.toFixed(2)}</td>
                    <td>{(r.cap_rate * 100).toFixed(2)}%</td>
                    <td>
                      <span
                        style={{
                          color: RECOMMENDATION_COLORS[r.recommendation] ?? '#6b7280',
                          fontWeight: 600,
                        }}
                      >
                        {RECOMMENDATION_LABELS[r.recommendation] ?? r.recommendation}
                      </span>
                    </td>
                    <td>{r.shocks.length > 0 ? r.shocks.join(', ') : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  )
}
