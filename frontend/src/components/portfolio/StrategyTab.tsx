import { useEffect, useState } from 'react'
import { api } from '../../utils/api'
import type {
  HoldingReconciliation,
  StrategyProfile,
  StrategyRunRecord,
} from '../../utils/types'

interface StrategyTabProps {
  portfolioId: string
}

type Phase = 'idle' | 'extracting' | 'review' | 'running' | 'done' | 'error'

const TRAJECTORIES = ['none', 'neighborhood_trajectory', 'displacement_pressure'] as const
const OUTLOOKS = ['neutral', 'bullish', 'bearish'] as const
const RISK_LEVELS = ['low', 'medium', 'high'] as const

const POLL_INTERVAL_MS = 800

function formatPercent(value?: number | null, digits = 1): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

function formatMoney(value?: number | null): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  })
}

export default function StrategyTab({ portfolioId }: StrategyTabProps) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [text, setText] = useState('')
  const [profile, setProfile] = useState<StrategyProfile | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [record, setRecord] = useState<StrategyRunRecord | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setPhase('idle')
    setText('')
    setProfile(null)
    setRunId(null)
    setRecord(null)
    setError('')
  }, [portfolioId])

  // Polling loop while a run is in flight.
  useEffect(() => {
    if (!runId || phase !== 'running') return
    let active = true
    const tick = async () => {
      try {
        const status = await api.strategy.status(runId)
        if (!active) return
        if (status.status === 'completed' || status.status === 'failed') {
          setRecord(status)
          setPhase(status.status === 'completed' ? 'done' : 'error')
          if (status.status === 'failed') {
            setError(status.error || 'Strategy run failed')
          }
        } else {
          setTimeout(tick, POLL_INTERVAL_MS)
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Status poll failed')
          setPhase('error')
        }
      }
    }
    void tick()
    return () => {
      active = false
    }
  }, [runId, phase])

  const onExtract = async () => {
    setError('')
    setPhase('extracting')
    try {
      const result = await api.strategy.extract({ portfolio_id: portfolioId, text })
      setProfile(result.profile)
      setPhase('review')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to extract profile')
      setPhase('error')
    }
  }

  const onRun = async () => {
    if (!profile) return
    setError('')
    setPhase('running')
    try {
      const started = await api.strategy.run({ portfolio_id: portfolioId, profile })
      setRunId(started.run_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start strategy run')
      setPhase('error')
    }
  }

  const onReset = () => {
    setPhase('idle')
    setProfile(null)
    setRunId(null)
    setRecord(null)
    setError('')
  }

  const updateAssumption = (k: keyof StrategyProfile['assumptions'], v: number) => {
    if (!profile) return
    setProfile({
      ...profile,
      assumptions: { ...profile.assumptions, [k]: v },
    })
  }

  const updatePolicy = (
    k: keyof StrategyProfile['policy_config'],
    v: number | string | boolean,
  ) => {
    if (!profile) return
    setProfile({
      ...profile,
      policy_config: { ...profile.policy_config, [k]: v as never },
    })
  }

  const updateThesis = (k: keyof StrategyProfile['thesis'], v: string) => {
    if (!profile) return
    setProfile({
      ...profile,
      thesis: { ...profile.thesis, [k]: v as never },
    })
  }

  return (
    <div className="strategy-tab" data-testid="strategy-tab">
      <section className="strategy-input">
        <h3>1. Describe your current investing strategy</h3>
        <textarea
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. Long-term buy and hold, low risk. Rents grow 4%/yr. 10-year hold. Protect tenants from displacement."
          data-testid="strategy-text"
        />
        <button
          type="button"
          onClick={() => void onExtract()}
          disabled={!text.trim() || phase === 'extracting' || phase === 'running'}
          data-testid="strategy-extract-btn"
        >
          {phase === 'extracting' ? 'Extracting…' : 'Extract profile'}
        </button>
      </section>

      {error && <p className="portfolio-error" data-testid="strategy-error">{error}</p>}

      {profile && (phase === 'review' || phase === 'running' || phase === 'done') && (
        <section className="strategy-profile" data-testid="strategy-profile">
          <h3>2. Review profile</h3>
          <p className="strategy-profile-hint">
            LLM seeded these fields — override anything before running.
          </p>

          <div className="strategy-profile-grid">
            <Field label="Rent growth">
              <input
                type="number"
                step="0.005"
                value={profile.assumptions.rent_growth}
                onChange={(e) => updateAssumption('rent_growth', Number(e.target.value))}
                disabled={phase !== 'review'}
                data-testid="profile-rent-growth"
              />
            </Field>
            <Field label="Expense growth">
              <input
                type="number"
                step="0.005"
                value={profile.assumptions.expense_growth}
                onChange={(e) => updateAssumption('expense_growth', Number(e.target.value))}
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="Vacancy">
              <input
                type="number"
                step="0.01"
                value={profile.assumptions.vacancy_rate}
                onChange={(e) => updateAssumption('vacancy_rate', Number(e.target.value))}
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="Hold years">
              <input
                type="number"
                step="1"
                value={profile.assumptions.hold_period_years}
                onChange={(e) =>
                  updateAssumption('hold_period_years', Number(e.target.value))
                }
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="Exit cap">
              <input
                type="number"
                step="0.005"
                value={profile.assumptions.exit_cap_rate}
                onChange={(e) => updateAssumption('exit_cap_rate', Number(e.target.value))}
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="Risk tolerance">
              <select
                value={profile.policy_config.risk_tolerance}
                onChange={(e) => updatePolicy('risk_tolerance', e.target.value)}
                disabled={phase !== 'review'}
              >
                {RISK_LEVELS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Refi threshold">
              <input
                type="number"
                step="0.005"
                value={profile.policy_config.refi_rate_threshold}
                onChange={(e) =>
                  updatePolicy('refi_rate_threshold', Number(e.target.value))
                }
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="Sell bias">
              <input
                type="number"
                step="0.1"
                value={profile.policy_config.sell_bias}
                onChange={(e) => updatePolicy('sell_bias', Number(e.target.value))}
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="Raise-rent bias">
              <input
                type="number"
                step="0.1"
                value={profile.policy_config.raise_rent_bias}
                onChange={(e) => updatePolicy('raise_rent_bias', Number(e.target.value))}
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="Tenant protection">
              <input
                type="checkbox"
                checked={profile.policy_config.tenant_protection}
                onChange={(e) => updatePolicy('tenant_protection', e.target.checked)}
                disabled={phase !== 'review'}
                data-testid="profile-tenant-protection"
              />
            </Field>
            <Field label="Trajectory">
              <select
                value={profile.thesis.trajectory}
                onChange={(e) => updateThesis('trajectory', e.target.value)}
                disabled={phase !== 'review'}
              >
                {TRAJECTORIES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Outlook">
              <select
                value={profile.thesis.market_outlook}
                onChange={(e) => updateThesis('market_outlook', e.target.value)}
                disabled={phase !== 'review'}
              >
                {OUTLOOKS.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          {phase === 'review' && (
            <button
              type="button"
              onClick={() => void onRun()}
              data-testid="strategy-run-btn"
            >
              Run analysis + simulation
            </button>
          )}
          {phase === 'running' && (
            <p className="portfolio-empty" data-testid="strategy-running">
              Running strategy — analysis + simulation in progress…
            </p>
          )}
        </section>
      )}

      {record && record.unified && phase === 'done' && (
        <section className="strategy-result" data-testid="strategy-result">
          <h3>3. Unified report</h3>
          <p
            className={`strategy-survives strategy-survives-${
              record.unified.survives ? 'yes' : 'no'
            }`}
          >
            {record.unified.survives
              ? `Strategy survives projection (confidence ${(
                  record.unified.confidence * 100
                ).toFixed(0)}%).`
              : `Strategy does not survive cleanly (confidence ${(
                  record.unified.confidence * 100
                ).toFixed(0)}%).`}
          </p>
          <p>{record.unified.summary}</p>

          {record.unified.agreements.length > 0 && (
            <>
              <h4>Agreements</h4>
              <ul>
                {record.unified.agreements.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </>
          )}

          {record.unified.divergences.length > 0 && (
            <>
              <h4>Divergences</h4>
              <ul>
                {record.unified.divergences.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </>
          )}

          <h4>Per-holding projection</h4>
          <table className="strategy-reconciliation">
            <thead>
              <tr>
                <th>Address</th>
                <th>Today</th>
                <th>Projected</th>
                <th>Projected value</th>
                <th>Projected cap</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {record.unified.reconciliations.map((r: HoldingReconciliation) => {
                const proj = record.simulation?.per_holding.find(
                  (p) => p.holding_id === r.holding_id,
                )
                return (
                  <tr
                    key={r.holding_id}
                    className={r.flipped ? 'flipped' : ''}
                    data-testid={`recon-${r.holding_id}`}
                  >
                    <td>{r.address}</td>
                    <td>{r.today_action}</td>
                    <td>{r.projected_action}</td>
                    <td>{formatMoney(proj?.projected_value)}</td>
                    <td>{formatPercent(proj?.projected_cap_rate)}</td>
                    <td>{r.note ?? ''}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <button type="button" onClick={onReset} data-testid="strategy-reset-btn">
            Start over
          </button>
        </section>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="strategy-field">
      <span>{label}</span>
      {children}
    </label>
  )
}
