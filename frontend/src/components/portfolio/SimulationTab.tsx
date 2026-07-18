import { useEffect, useState } from 'react'
import { api } from '../../utils/api'
import {
  formatJpyCompact,
  formatMarketOutlookLabel,
  formatRecommendationLabel,
  formatRiskToleranceLabel,
  formatTrajectoryLabel,
} from '../../utils/japan'
import type {
  HoldingReconciliation,
  StrategyProfile,
  StrategyRunRecord,
} from '../../utils/types'

interface SimulationTabProps {
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
  return formatJpyCompact(value)
}

export default function SimulationTab({ portfolioId }: SimulationTabProps) {
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
            setError(status.error || 'シミュレーションの実行に失敗しました。')
          }
        } else {
          setTimeout(tick, POLL_INTERVAL_MS)
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : '実行状況の取得に失敗しました。')
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
      setError(err instanceof Error ? err.message : '投資方針を抽出できませんでした。')
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
      setError(err instanceof Error ? err.message : 'シミュレーションを開始できませんでした。')
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
        <h3>1. 運用方針を入力</h3>
        <textarea
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="例: 東京23区の区分マンションを長期保有。空室率は低め、家賃は年2%成長想定。5〜10年保有。"
          data-testid="strategy-text"
        />
        <button
          type="button"
          onClick={() => void onExtract()}
          disabled={!text.trim() || phase === 'extracting' || phase === 'running'}
          data-testid="strategy-extract-btn"
        >
          {phase === 'extracting' ? '抽出中…' : '方針を抽出'}
        </button>
      </section>

      {error && <p className="portfolio-error" data-testid="strategy-error">{error}</p>}

      {profile && (phase === 'review' || phase === 'running' || phase === 'done') && (
        <section className="strategy-profile" data-testid="strategy-profile">
          <h3>2. 前提条件を確認</h3>
          <p className="strategy-profile-hint">
            抽出された前提条件を日本の運用実態に合わせて調整してから実行できます。
          </p>

          <div className="strategy-profile-grid">
            <Field label="賃料成長率">
              <input
                type="number"
                step="0.005"
                value={profile.assumptions.rent_growth}
                onChange={(e) => updateAssumption('rent_growth', Number(e.target.value))}
                disabled={phase !== 'review'}
                data-testid="profile-rent-growth"
              />
            </Field>
            <Field label="費用成長率">
              <input
                type="number"
                step="0.005"
                value={profile.assumptions.expense_growth}
                onChange={(e) => updateAssumption('expense_growth', Number(e.target.value))}
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="空室率">
              <input
                type="number"
                step="0.01"
                value={profile.assumptions.vacancy_rate}
                onChange={(e) => updateAssumption('vacancy_rate', Number(e.target.value))}
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="保有年数">
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
            <Field label="出口利回り">
              <input
                type="number"
                step="0.005"
                value={profile.assumptions.exit_cap_rate}
                onChange={(e) => updateAssumption('exit_cap_rate', Number(e.target.value))}
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="リスク許容度">
              <select
                value={profile.policy_config.risk_tolerance}
                onChange={(e) => updatePolicy('risk_tolerance', e.target.value)}
                disabled={phase !== 'review'}
              >
                {RISK_LEVELS.map((r) => (
                  <option key={r} value={r}>
                    {formatRiskToleranceLabel(r)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="借換しきい値">
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
            <Field label="売却寄り判断">
              <input
                type="number"
                step="0.1"
                value={profile.policy_config.sell_bias}
                onChange={(e) => updatePolicy('sell_bias', Number(e.target.value))}
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="賃料改定寄り判断">
              <input
                type="number"
                step="0.1"
                value={profile.policy_config.raise_rent_bias}
                onChange={(e) => updatePolicy('raise_rent_bias', Number(e.target.value))}
                disabled={phase !== 'review'}
              />
            </Field>
            <Field label="入居者配慮">
              <input
                type="checkbox"
                checked={profile.policy_config.tenant_protection}
                onChange={(e) => updatePolicy('tenant_protection', e.target.checked)}
                disabled={phase !== 'review'}
                data-testid="profile-tenant-protection"
              />
            </Field>
            <Field label="エリア推移">
              <select
                value={profile.thesis.trajectory}
                onChange={(e) => updateThesis('trajectory', e.target.value)}
                disabled={phase !== 'review'}
              >
                {TRAJECTORIES.map((t) => (
                  <option key={t} value={t}>
                    {formatTrajectoryLabel(t)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="市況見通し">
              <select
                value={profile.thesis.market_outlook}
                onChange={(e) => updateThesis('market_outlook', e.target.value)}
                disabled={phase !== 'review'}
              >
                {OUTLOOKS.map((o) => (
                  <option key={o} value={o}>
                    {formatMarketOutlookLabel(o)}
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
              分析とシミュレーションを実行
            </button>
          )}
          {phase === 'running' && (
            <p className="portfolio-empty" data-testid="strategy-running">
              シミュレーションを実行中です…
            </p>
          )}
        </section>
      )}

      {record && record.unified && phase === 'done' && (
        <section className="strategy-result" data-testid="strategy-result">
          <h3>3. 統合レポート</h3>
          <p
            className={`strategy-survives strategy-survives-${
              record.unified.survives ? 'yes' : 'no'
            }`}
          >
            {record.unified.survives
              ? `運用方針は将来試算に耐えうる見込みです（確信度 ${(
                  record.unified.confidence * 100
                ).toFixed(0)}%）。`
              : `運用方針は追加調整が必要です（確信度 ${(
                  record.unified.confidence * 100
                ).toFixed(0)}%）。`}
          </p>
          <p>{record.unified.summary}</p>

          {record.unified.agreements.length > 0 && (
            <>
              <h4>一致ポイント</h4>
              <ul>
                {record.unified.agreements.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </>
          )}

          {record.unified.divergences.length > 0 && (
            <>
              <h4>差分ポイント</h4>
              <ul>
                {record.unified.divergences.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </>
          )}

          <h4>物件別の将来試算</h4>
          <table className="strategy-reconciliation">
            <thead>
              <tr>
                <th>所在地</th>
                <th>現在判断</th>
                <th>将来判断</th>
                <th>将来評価額</th>
                <th>将来NOI</th>
                <th>将来CF</th>
                <th>将来利回り</th>
                <th>補足</th>
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
                    <td>{formatRecommendationLabel(r.today_action)}</td>
                    <td>{formatRecommendationLabel(r.projected_action)}</td>
                    <td>{formatMoney(proj?.projected_value)}</td>
                    <td data-testid={`recon-noi-${r.holding_id}`}>{formatMoney(proj?.projected_annual_noi)}</td>
                    <td data-testid={`recon-cf-${r.holding_id}`}>{formatMoney(proj?.projected_monthly_cash_flow)}</td>
                    <td>{formatPercent(proj?.projected_cap_rate)}</td>
                    <td>{r.note ?? ''}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <button type="button" onClick={onReset} data-testid="strategy-reset-btn">
            もう一度実行
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
