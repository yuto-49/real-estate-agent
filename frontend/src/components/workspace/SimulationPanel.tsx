import { useCallback, useEffect, useState } from 'react'
import RentComps from '../RentComps'

interface UnderwritingResult {
  noi: number
  cap_rate: number
  cash_on_cash: number
  dscr: number
  irr: number
  monthly_pi: number
}

interface StressResult {
  median_irr: number
  p10_irr: number
  p90_irr: number
  fail_rate: number
}

interface SimulationPanelProps {
  propertyId: string | null
  visible: boolean
}

export default function SimulationPanel({ propertyId, visible }: SimulationPanelProps) {
  const [underwriting, setUnderwriting] = useState<UnderwritingResult | null>(null)
  const [stress, setStress] = useState<StressResult | null>(null)
  const [uwLoading, setUwLoading] = useState(false)
  const [stressLoading, setStressLoading] = useState(false)

  const runUnderwriting = useCallback(async () => {
    if (!propertyId) return
    setUwLoading(true)
    try {
      const resp = await fetch(`/api/underwrite/${propertyId}`, { method: 'POST' })
      if (resp.ok) {
        const data = await resp.json()
        setUnderwriting(data.outputs ?? data)
      }
    } catch { /* empty state handles */ }
    finally { setUwLoading(false) }
  }, [propertyId])

  const runStress = useCallback(async () => {
    if (!propertyId) return
    setStressLoading(true)
    try {
      const resp = await fetch(`/api/underwrite/${propertyId}/stress`, { method: 'POST' })
      if (resp.ok) {
        const data = await resp.json()
        setStress(data)
      }
    } catch { /* empty state handles */ }
    finally { setStressLoading(false) }
  }, [propertyId])

  useEffect(() => {
    if (propertyId && visible) {
      void runUnderwriting()
    }
  }, [propertyId, visible, runUnderwriting])

  const pct = (v: number | undefined) => v != null ? `${(v * 100).toFixed(1)}%` : '-'
  const yen = (v: number | undefined) => v != null ? `${Math.round(v).toLocaleString()}円` : '-'

  if (!propertyId) {
    return (
      <>
        <div className="workspace-panel-header">Simulation</div>
        <div className="ws-empty">
          <div className="ws-empty-icon">📊</div>
          <p>Analysis results will appear here after you analyze a property.</p>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="workspace-panel-header">Simulation</div>

      <div className="ws-card">
        <div className="ws-card-title">Underwriting</div>
        {uwLoading ? (
          <div className="ws-loading"><div className="ws-spinner" /></div>
        ) : underwriting ? (
          <>
            <div className="ws-property-stat"><span className="ws-property-stat-label">Cap Rate</span><span className="ws-property-stat-value">{pct(underwriting.cap_rate)}</span></div>
            <div className="ws-property-stat"><span className="ws-property-stat-label">Cash-on-Cash</span><span className="ws-property-stat-value">{pct(underwriting.cash_on_cash)}</span></div>
            <div className="ws-property-stat"><span className="ws-property-stat-label">DSCR</span><span className="ws-property-stat-value">{underwriting.dscr?.toFixed(2) ?? '-'}</span></div>
            <div className="ws-property-stat"><span className="ws-property-stat-label">IRR</span><span className="ws-property-stat-value">{pct(underwriting.irr)}</span></div>
            <div className="ws-property-stat"><span className="ws-property-stat-label">NOI</span><span className="ws-property-stat-value">{yen(underwriting.noi)}</span></div>
            <div className="ws-property-stat"><span className="ws-property-stat-label">Monthly P&I</span><span className="ws-property-stat-value">{yen(underwriting.monthly_pi)}</span></div>
          </>
        ) : (
          <p style={{ fontSize: 13, color: '#94a3b8' }}>No data yet</p>
        )}
      </div>

      <div className="ws-card">
        <div className="ws-card-title">Stress Test (Monte Carlo)</div>
        {stressLoading ? (
          <div className="ws-loading"><div className="ws-spinner" /></div>
        ) : stress ? (
          <>
            <div className="ws-property-stat"><span className="ws-property-stat-label">Median IRR</span><span className="ws-property-stat-value">{pct(stress.median_irr)}</span></div>
            <div className="ws-property-stat"><span className="ws-property-stat-label">P10 (worst)</span><span className="ws-property-stat-value">{pct(stress.p10_irr)}</span></div>
            <div className="ws-property-stat"><span className="ws-property-stat-label">P90 (best)</span><span className="ws-property-stat-value">{pct(stress.p90_irr)}</span></div>
            <div className="ws-property-stat">
              <span className="ws-property-stat-label">Fail Rate</span>
              <span className="ws-property-stat-value">
                <span className={`ws-badge ${stress.fail_rate > 0.2 ? 'ws-badge--red' : stress.fail_rate > 0.1 ? 'ws-badge--amber' : 'ws-badge--green'}`}>{pct(stress.fail_rate)}</span>
              </span>
            </div>
          </>
        ) : (
          <>
            <p style={{ fontSize: 13, color: '#94a3b8' }}>Run 300 Monte Carlo scenarios</p>
            <button className="ws-btn-primary" onClick={() => void runStress()} disabled={stressLoading}>Run Stress Test</button>
          </>
        )}
      </div>

      <div className="ws-card">
        <div className="ws-card-title">Rent Comps</div>
        <RentComps propertyId={propertyId} />
      </div>
    </>
  )
}
