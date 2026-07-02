import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import MarketSimulationMap from './MarketSimulationMap'
import SimulationPersonaCard from './SimulationPersonaCard'
import { api } from '../utils/api'
import type {
  InvestorDecisionTrace,
  MarketInvestorPersona,
  MarketSimulationReplay,
  MarketSimulationRunResult,
  MarketSimulationRunStatus,
  MarketSimulationScope,
  Property,
} from '../utils/types'

const PLAYBACK_SPEEDS = [0.75, 1, 1.5, 2]

const COHORT_PRESET_DETAILS: Record<string, {
  label: string
  description: string
  archetypes: string[]
}> = {
  balanced: {
    label: 'バランス型',
    description: 'バリュー投資家、利回り重視型、モメンタム追随型、逆張り型をバランスよく配置し、多様な市場動向を再現します。',
    archetypes: ['value', 'yield', 'momentum', 'contrarian'],
  },
  income: {
    label: 'インカム重視型',
    description: 'キャッシュフロー・安定性・下値リスク防御を重視する賃貸収益志向の買い手を多めに配置します。',
    archetypes: ['yield', 'yield', 'value', 'contrarian'],
  },
  momentum: {
    label: 'モメンタム追随型',
    description: '注目度の急上昇や他投資家の動向に素早く反応する、トレンド追随型の投資家を多めに配置します。',
    archetypes: ['momentum', 'momentum', 'value', 'yield'],
  },
}

type SimulationStage = 'configure' | 'personas' | 'running' | 'replay'

export default function MarketSimulationWorkspace() {
  const [searchParams, setSearchParams] = useSearchParams()
  const focusPropertyId = searchParams.get('property_id')
  const focusPropertyAddress = searchParams.get('address')

  const [properties, setProperties] = useState<Property[]>([])
  const [stage, setStage] = useState<SimulationStage>('configure')
  const [runId, setRunId] = useState('')
  const [runLabel, setRunLabel] = useState('東京投資家シミュレーション')
  const [cohortPreset, setCohortPreset] = useState('balanced')
  const [investorCount, setInvestorCount] = useState(8)
  const [tickCount, setTickCount] = useState(8)
  const [propertyType, setPropertyType] = useState('')
  const [zipCode, setZipCode] = useState('')
  const [minPrice, setMinPrice] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [loading, setLoading] = useState(false)
  const [personaLoading, setPersonaLoading] = useState(false)
  const [status, setStatus] = useState<MarketSimulationRunStatus | null>(null)
  const [result, setResult] = useState<MarketSimulationRunResult | null>(null)
  const [replay, setReplay] = useState<MarketSimulationReplay | null>(null)
  const [personas, setPersonas] = useState<MarketInvestorPersona[]>([])
  const [inventorySummary, setInventorySummary] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState('')
  const [selectedPropertyId, setSelectedPropertyId] = useState<string | null>(null)
  const [selectedInvestorId, setSelectedInvestorId] = useState<string | null>(null)
  const [currentTickIndex, setCurrentTickIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)

  useEffect(() => {
    let active = true
    api.properties.list().then((data) => {
      if (!active) return
      setProperties(data.properties as Property[])
    }).catch(() => {
      if (active) setProperties([])
    })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!isPlaying || !replay || replay.ticks.length === 0) return
    const timeout = window.setTimeout(() => {
      setCurrentTickIndex((current) => {
        if (current >= replay.ticks.length - 1) {
          setIsPlaying(false)
          return current
        }
        return current + 1
      })
    }, Math.max(350, 1200 / playbackSpeed))
    return () => window.clearTimeout(timeout)
  }, [currentTickIndex, isPlaying, playbackSpeed, replay])

  const filteredProperties = useMemo(() => {
    return properties.filter((property) => {
      const zip = String((property as Property & { neighborhood_data?: Record<string, unknown> }).neighborhood_data?.zip_code || '')
      const price = Number(property.asking_price || 0)
      if (focusPropertyId && property.id !== focusPropertyId) return false
      if (propertyType && property.property_type !== propertyType) return false
      if (zipCode && zip !== zipCode.trim()) return false
      if (minPrice && price < Number(minPrice)) return false
      if (maxPrice && price > Number(maxPrice)) return false
      return true
    })
  }, [focusPropertyId, maxPrice, minPrice, properties, propertyType, zipCode])

  const propertyTypes = useMemo(() => {
    return Array.from(new Set(properties.map((property) => property.property_type).filter(Boolean) as string[])).sort()
  }, [properties])

  const cohortPresetDetail = COHORT_PRESET_DETAILS[cohortPreset] || COHORT_PRESET_DETAILS.balanced
  const plannedPersonaTypes = useMemo(() => {
    const archetypes = cohortPresetDetail.archetypes
    return Array.from({ length: investorCount }, (_, index) => archetypes[index % archetypes.length])
  }, [cohortPresetDetail, investorCount])
  const plannedPersonaCounts = useMemo(() => {
    return plannedPersonaTypes.reduce<Record<string, number>>((accumulator, archetype) => {
      accumulator[archetype] = (accumulator[archetype] || 0) + 1
      return accumulator
    }, {})
  }, [plannedPersonaTypes])

  useEffect(() => {
    setPersonas([])
    setInventorySummary(null)
    if (stage === 'personas') setStage('configure')
  }, [cohortPreset, focusPropertyId, investorCount, maxPrice, minPrice, propertyType, zipCode])

  const currentTick = replay?.ticks[currentTickIndex] ?? null
  const propertyStates = currentTick?.property_states ?? []
  const selectedProperty = propertyStates.find((property) => property.property_id === selectedPropertyId) ?? propertyStates[0] ?? null
  const selectedInvestor = replay?.investors.find((investor) => investor.id === selectedInvestorId) ?? replay?.investors[0] ?? null

  const propertyDecisions = useMemo(() => {
    const decisions = currentTick?.decisions ?? []
    const activePropertyId = selectedProperty?.property_id
    return decisions
      .filter((decision) => decision.property_id === activePropertyId)
      .sort((left, right) => (Number(right.total_score || 0) - Number(left.total_score || 0)))
  }, [currentTick?.decisions, selectedProperty?.property_id])

  const investorDecision = useMemo(() => {
    if (!currentTick || !selectedInvestor) return null
    return currentTick.decisions.find((decision) => decision.investor_id === selectedInvestor.id) ?? null
  }, [currentTick, selectedInvestor])

  const investorHistory = useMemo(() => {
    if (!replay || !selectedInvestor) return []
    return replay.ticks
      .map((tick) => tick.decisions.find((decision) => decision.investor_id === selectedInvestor.id))
      .filter((decision): decision is InvestorDecisionTrace => Boolean(decision))
  }, [replay, selectedInvestor])

  const previousInvestorDecision = useMemo(() => {
    if (!replay || !selectedInvestor || currentTickIndex <= 0) return null
    return replay.ticks[currentTickIndex - 1]?.decisions.find((decision) => decision.investor_id === selectedInvestor.id) ?? null
  }, [currentTickIndex, replay, selectedInvestor])

  useEffect(() => {
    if (!replay || replay.ticks.length === 0) return
    const firstTick = replay.ticks[0]
    if (!selectedPropertyId && firstTick.property_states.length > 0) {
      setSelectedPropertyId(firstTick.property_states[0].property_id)
    }
    if (!selectedInvestorId && replay.investors.length > 0) {
      setSelectedInvestorId(replay.investors[0].id)
    }
  }, [replay, selectedInvestorId, selectedPropertyId])

  const buildScope = (): Partial<MarketSimulationScope> => {
    const scope: Partial<MarketSimulationScope> = { include_pending: false }
    if (focusPropertyId) scope.property_ids = [focusPropertyId]
    if (propertyType) scope.property_types = [propertyType]
    if (zipCode.trim()) scope.zip_codes = [zipCode.trim()]
    if (minPrice) scope.min_price = Number(minPrice)
    if (maxPrice) scope.max_price = Number(maxPrice)
    return scope
  }

  const resetRun = () => {
    setStage('configure')
    setRunId('')
    setStatus(null)
    setResult(null)
    setReplay(null)
    setCurrentTickIndex(0)
    setIsPlaying(false)
    setSelectedInvestorId(null)
    setSelectedPropertyId(null)
    setError('')
  }

  const generatePersonas = async () => {
    setError('')
    setPersonaLoading(true)
    try {
      const preview = await api.marketSimulation.generatePersonas({
        investor_count: investorCount,
        cohort_preset: cohortPreset,
        scope: buildScope(),
      })
      setPersonas(preview.personas)
      setInventorySummary(preview.inventory_summary)
      setStage('personas')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate investor personas')
    } finally {
      setPersonaLoading(false)
    }
  }

  const startRun = async () => {
    setError('')
    setLoading(true)
    setStage('running')
    setStatus(null)
    setResult(null)
    setReplay(null)
    try {
      const started = await api.marketSimulation.start({
        investor_count: investorCount,
        tick_count: tickCount,
        cohort_preset: cohortPreset,
        run_label: runLabel.trim() || undefined,
        scope: buildScope(),
        seeded_personas: personas,
      })
      setRunId(started.run_id)

      let completedStatus: MarketSimulationRunStatus | null = null
      for (let attempt = 0; attempt < 60; attempt += 1) {
        const nextStatus = await api.marketSimulation.status(started.run_id)
        setStatus(nextStatus)
        if (nextStatus.status === 'completed') {
          completedStatus = nextStatus
          break
        }
        if (nextStatus.status === 'failed') {
          throw new Error(nextStatus.error_message || 'Market simulation failed')
        }
        await new Promise((resolve) => window.setTimeout(resolve, 450))
      }

      if (!completedStatus) {
        throw new Error('Timed out waiting for the investor simulation to finish')
      }

      const [nextResult, nextReplay] = await Promise.all([
        api.marketSimulation.result(started.run_id),
        api.marketSimulation.replay(started.run_id),
      ])
      setResult(nextResult)
      setReplay(nextReplay)
      setCurrentTickIndex(0)
      setStage('replay')
      if (nextReplay.ticks[0]?.property_states[0]) {
        setSelectedPropertyId(nextReplay.ticks[0].property_states[0].property_id)
      }
      if (nextReplay.investors[0]) {
        setSelectedInvestorId(nextReplay.investors[0].id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start the investor market simulation')
      setStage(personas.length > 0 ? 'personas' : 'configure')
    } finally {
      setLoading(false)
    }
  }

  const clearFocusedProperty = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('property_id')
    next.delete('address')
    next.delete('price')
    setSearchParams(next)
  }

  const eligiblePriceRange = useMemo(() => {
    if (filteredProperties.length === 0) return '対象物件なし'
    const prices = filteredProperties.map((property) => Number(property.asking_price || 0)).sort((left, right) => left - right)
    return `${formatCurrency(prices[0])} - ${formatCurrency(prices[prices.length - 1])}`
  }, [filteredProperties])

  const topDrivers = useMemo(() => deriveTopDrivers(investorDecision), [investorDecision])
  const signalChanges = useMemo(() => deriveSignalChanges(investorDecision, previousInvestorDecision), [investorDecision, previousInvestorDecision])
  const riskNotes = useMemo(() => deriveRiskNotes(investorDecision), [investorDecision])

  return (
    <div className="market-sim-shell">
      <div className="market-sim-header">
        <div>
          <h2>投資家マーケットシミュレーション</h2>
          <p>
            市場スコープを設定し、投資家ペルソナを生成。シグナルや競合圧力の変化に応じて、
            投資家がどのように注目・入札・撤退するかをリプレイで再現します。
          </p>
        </div>
        {stage !== 'configure' && (
          <button type="button" className="secondary-btn" onClick={resetRun}>新規シミュレーション</button>
        )}
      </div>

      <div className="sim-step-indicator sim-step-indicator--wide">
        <span className={`sim-step ${stage === 'configure' ? 'active' : 'done'}`}>1. スコープ設定</span>
        <span className="sim-step-arrow">→</span>
        <span className={`sim-step ${stage === 'personas' ? 'active' : stage === 'running' || stage === 'replay' ? 'done' : ''}`}>2. ペルソナ確認</span>
        <span className="sim-step-arrow">→</span>
        <span className={`sim-step ${stage === 'running' ? 'active' : stage === 'replay' ? 'done' : ''}`}>3. 実行</span>
        <span className="sim-step-arrow">→</span>
        <span className={`sim-step ${stage === 'replay' ? 'active' : ''}`}>4. リプレイ</span>
      </div>

      {focusPropertyId && (
        <div className="market-sim-focus-banner">
          <div>
            <strong>フォーカス物件指定</strong>
            <p>{focusPropertyAddress || 'ダッシュボードで選択された物件'}を基準にシミュレーションを実行します。</p>
          </div>
          <button type="button" className="secondary-btn" onClick={clearFocusedProperty}>フォーカス解除</button>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      {stage === 'configure' && (
        <div className="market-sim-config-grid">
          <section className="market-sim-surface">
            <div className="market-sim-section-heading">
              <div>
                <h3>マーケットスコープ</h3>
                <p>シミュレーション対象となる物件の範囲を設定します。</p>
              </div>
            </div>

            <div className="market-sim-form-grid">
              <label className="agent-control-group">
                <span>実行ラベル</span>
                <input value={runLabel} onChange={(event) => setRunLabel(event.target.value)} />
              </label>
              <label className="agent-control-group">
                <span>コホートプリセット</span>
                <select value={cohortPreset} onChange={(event) => setCohortPreset(event.target.value)}>
                  <option value="balanced">バランス型</option>
                  <option value="income">インカム重視型</option>
                  <option value="momentum">モメンタム追随型</option>
                </select>
              </label>
              <label className="agent-control-group">
                <span>投資家数</span>
                <input type="number" min={1} max={40} value={investorCount} onChange={(event) => setInvestorCount(Number(event.target.value))} />
              </label>
              <label className="agent-control-group">
                <span>ティック数</span>
                <input type="number" min={1} max={20} value={tickCount} onChange={(event) => setTickCount(Number(event.target.value))} />
              </label>
              <label className="agent-control-group">
                <span>物件種別</span>
                <select value={propertyType} onChange={(event) => setPropertyType(event.target.value)}>
                  <option value="">全物件</option>
                  {propertyTypes.map((type) => <option key={type} value={type}>{type}</option>)}
                </select>
              </label>
              <label className="agent-control-group">
                <span>最低価格</span>
                <input type="number" placeholder="10000000" value={minPrice} onChange={(event) => setMinPrice(event.target.value)} />
              </label>
              <label className="agent-control-group">
                <span>最高価格</span>
                <input type="number" placeholder="200000000" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} />
              </label>
            </div>

            <div className="market-sim-preset-preview">
              <div className="market-sim-preset-preview__header">
                <div>
                  <strong>{cohortPresetDetail.label} preset</strong>
                  <p>{cohortPresetDetail.description}</p>
                </div>
                <span>{investorCount}名のペルソナを計画</span>
              </div>
              <div className="market-sim-chip-group">
                {Object.entries(plannedPersonaCounts).map(([archetype, count]) => (
                  <span key={archetype} className={`market-sim-chip market-sim-chip--${archetype}`}>
                    {archetype} x {count}
                  </span>
                ))}
              </div>
              <div className="market-sim-planned-types">
                {plannedPersonaTypes.map((archetype, index) => (
                  <span key={`${archetype}-${index}`} className={`market-sim-planned-type market-sim-planned-type--${archetype}`}>
                    投資家{index + 1}: {archetype}
                  </span>
                ))}
              </div>
              {personaLoading && (
                <p className="market-sim-inline-note">現在のマーケットスコープと在庫構成に基づき、ペルソナを生成中です。</p>
              )}
            </div>

            <div className="market-sim-summary-row">
              <MetricCard label="対象物件数" value={String(filteredProperties.length)} />
              <MetricCard label="価格帯" value={eligiblePriceRange} />
              <MetricCard label="リプレイステップ" value={String(tickCount)} />
            </div>

            <div className="market-sim-callout">
              <strong>次のステップ</strong>
              <p>
                設定したスコープに合う投資家コホートを生成し、利回り・エリア評価・リスク・
                競合動向に基づく注目・入札・撤退・取得の動きをリプレイで再現します。
              </p>
            </div>

            <div className="market-sim-actions">
              <button type="button" className="primary-btn" onClick={() => void generatePersonas()} disabled={personaLoading || filteredProperties.length === 0}>
                {personaLoading ? 'ペルソナ生成中…' : '投資家ペルソナを生成'}
              </button>
            </div>
          </section>

          <section className="market-sim-surface market-sim-surface--inventory">
            <div className="market-sim-section-heading">
              <div>
                <h3>対象物件一覧</h3>
                <p>シミュレーション開始後にコホートが評価する物件です。</p>
              </div>
              <span>{filteredProperties.length}件</span>
            </div>
            <div className="market-sim-property-list">
              {filteredProperties.slice(0, 24).map((property) => (
                <button
                  key={property.id}
                  type="button"
                  className={`market-sim-property-row ${focusPropertyId === property.id ? 'is-focused' : ''}`}
                >
                  <strong>{property.address}</strong>
                  <span>{formatCurrency(Number(property.asking_price || 0))} • {property.property_type || '種別不明'}</span>
                </button>
              ))}
              {filteredProperties.length === 0 && (
                <div className="market-sim-empty-copy">現在のフィルター条件に一致する物件がありません。</div>
              )}
            </div>
          </section>
        </div>
      )}

      {stage === 'personas' && (
        <div className="market-sim-persona-stage">
          <section className="market-sim-surface">
            <div className="market-sim-section-heading">
              <div>
                <h3>投資家ペルソナ確認</h3>
                <p>シミュレーション実行前に、各投資家の特性と最適化対象を確認してください。</p>
              </div>
              <span>{personas.length}名</span>
            </div>
            <div className="market-sim-persona-summary">
              <MetricCard label="対象物件数" value={String(inventorySummary?.property_count || filteredProperties.length)} />
              <MetricCard label="コホートプリセット" value={cohortPresetDetail.label} />
              <MetricCard label="投資家数" value={String(personas.length)} />
            </div>
            <div className="market-sim-persona-grid">
              {personas.map((persona) => (
                <SimulationPersonaCard
                  key={persona.display_name}
                  badge={persona.archetype.toUpperCase()}
                  badgeTone="investor"
                  name={persona.display_name}
                  subtitle={`${persona.risk_posture} • ${persona.preferred_price_band}`}
                  traits={[
                    { label: '予算', value: formatCurrency(persona.budget) },
                    { label: '保有期間', value: persona.hold_horizon },
                    { label: '目標利回り', value: persona.target_yield },
                    { label: '競合スタイル', value: persona.competition_style },
                  ]}
                  summary={<p>{persona.investment_thesis}</p>}
                  lists={[
                    { label: '物件種別', items: persona.preferred_property_types },
                    { label: '希望エリア', items: persona.neighborhood_preferences },
                    { label: '回避条件', items: persona.avoidance_triggers },
                  ]}
                  footer={<p>出口戦略: {persona.exit_style}</p>}
                />
              ))}
            </div>
            <div className="market-sim-actions market-sim-actions--split">
              <button type="button" className="secondary-btn" onClick={() => setStage('configure')}>スコープに戻る</button>
              <div className="market-sim-actions market-sim-actions--inline">
                <button type="button" className="secondary-btn" onClick={() => void generatePersonas()} disabled={personaLoading}>
                  {personaLoading ? '再生成中…' : 'ペルソナ再生成'}
                </button>
                <button type="button" className="primary-btn" onClick={() => void startRun()} disabled={loading || personas.length !== investorCount}>
                  {loading ? '開始中…' : 'シミュレーション開始'}
                </button>
              </div>
            </div>
          </section>
        </div>
      )}

      {stage === 'running' && (
        <div className="market-sim-surface market-sim-running-stage">
          <div className="market-sim-running-header">
            <div>
              <h3>マーケットシミュレーション実行中</h3>
              <p>
                {status?.run_label || runLabel || 'Investor run'} • {status?.investor_count || investorCount} investors • {status?.property_count || filteredProperties.length} properties
              </p>
            </div>
            <span>{status?.progress || 0}%</span>
          </div>
          <div className="market-sim-progress-track">
            <div className="market-sim-progress-bar" style={{ width: `${status?.progress || 0}%` }} />
          </div>
          <div className="market-sim-summary-row">
            <MetricCard label="現在のティック" value={`${status?.current_tick || 0} / ${status?.total_ticks || tickCount}`} />
            <MetricCard label="投資家数" value={String(status?.investor_count || investorCount)} />
            <MetricCard label="対象物件数" value={String(status?.property_count || filteredProperties.length)} />
            <MetricCard label="実行ID" value={runId ? `${runId.slice(0, 12)}…` : '準備中'} />
          </div>
        </div>
      )}

      {stage === 'replay' && replay && result && currentTick && (
        <div className="market-sim-replay-stage">
          <div className="market-sim-summary-row">
            <MetricCard label="完了ティック" value={String(result.completed_ticks)} />
            <MetricCard label="取得件数" value={String(result.acquisitions.length)} />
            <MetricCard label="意思決定数" value={String(result.summary.decision_count || 0)} />
            <MetricCard label="市場温度" value={formatScore(Number(result.summary.market_temperature || 0))} />
          </div>

          <section className="market-sim-surface market-sim-replay-controls">
            <div className="market-sim-replay-toolbar">
              <button type="button" className="primary-btn" onClick={() => setIsPlaying((current) => !current)}>
                {isPlaying ? '一時停止' : '再生'}
              </button>
              <button type="button" className="secondary-btn" onClick={() => setCurrentTickIndex((current) => Math.max(0, current - 1))}>前のティック</button>
              <button type="button" className="secondary-btn" onClick={() => setCurrentTickIndex((current) => Math.min(replay.ticks.length - 1, current + 1))}>次のティック</button>
              <label className="market-sim-speed-select">
                <span>速度</span>
                <select value={playbackSpeed} onChange={(event) => setPlaybackSpeed(Number(event.target.value))}>
                  {PLAYBACK_SPEEDS.map((speed) => <option key={speed} value={speed}>{speed}x</option>)}
                </select>
              </label>
              <div className="market-sim-toolbar-tick">ティック {currentTickIndex + 1} / {replay.ticks.length}</div>
            </div>
            <input
              type="range"
              min={0}
              max={Math.max(0, replay.ticks.length - 1)}
              value={currentTickIndex}
              onChange={(event) => {
                setCurrentTickIndex(Number(event.target.value))
                setIsPlaying(false)
              }}
            />
          </section>

          <div className="market-sim-replay-grid">
            <section className="market-sim-surface market-sim-surface--map">
              <MarketSimulationMap
                states={propertyStates}
                selectedPropertyId={selectedProperty?.property_id || null}
                onSelectProperty={setSelectedPropertyId}
              />
            </section>

            <section className="market-sim-surface market-sim-surface--panel">
              <div className="market-sim-section-heading">
                <div>
                  <h3>物件パネル</h3>
                  <p>{selectedProperty?.address || '地図上の物件を選択して動向を確認してください。'}</p>
                </div>
                {selectedProperty ? <span className={`market-sim-status-pill market-sim-status-pill--${selectedProperty.status}`}>{selectedProperty.status}</span> : null}
              </div>
              {selectedProperty ? (
                <>
                  <div className="market-sim-stat-grid">
                    <StatRow label="売出価格" value={formatCurrency(Number(selectedProperty.asking_price || 0))} />
                    <StatRow label="最高入札額" value={selectedProperty.top_bid != null ? formatCurrency(Number(selectedProperty.top_bid)) : 'なし'} />
                    <StatRow label="注目度" value={String(selectedProperty.attention_count)} />
                    <StatRow label="競合度" value={selectedProperty.local_competition.toFixed(1)} />
                    <StatRow label="入札速度" value={formatSignedCurrency(selectedProperty.bid_velocity)} />
                    <StatRow label="成約閾値" value={formatCurrency(Number(selectedProperty.reservation_threshold || 0))} />
                  </div>
                  <div className="market-sim-target-list">
                    <strong>この物件を狙う投資家</strong>
                    <div className="market-sim-scroll-list">
                      {propertyDecisions.map((decision) => (
                        <button
                          key={`${decision.investor_id}-${decision.tick_num}`}
                          type="button"
                          onClick={() => setSelectedInvestorId(decision.investor_id)}
                          className={`market-sim-target-row ${selectedInvestor?.id === decision.investor_id ? 'is-active' : ''}`}
                        >
                          <div className="market-sim-target-row__header">
                            <strong>{decision.investor_name}</strong>
                            <span className={`market-sim-action-pill market-sim-action-pill--${decision.chosen_action}`}>{decision.chosen_action}</span>
                          </div>
                          <p>{decision.chosen_action_reason}</p>
                          <span>
                            Score {formatScore(Number(decision.total_score || 0))}
                            {decision.bid_amount != null ? ` • Bid ${formatCurrency(Number(decision.bid_amount))}` : ''}
                          </span>
                        </button>
                      ))}
                      {propertyDecisions.length === 0 && <div className="market-sim-empty-copy">現在のティックでこの物件を狙う投資家はいません。</div>}
                    </div>
                  </div>
                </>
              ) : (
                <div className="market-sim-empty-copy">地図上の物件マーカーを選択すると、どの投資家が集中しているか確認できます。</div>
              )}
            </section>

            <section className="market-sim-surface market-sim-surface--panel market-sim-surface--investor">
              <div className="market-sim-section-heading">
                <div>
                  <h3>投資家パネル</h3>
                  <p>{selectedInvestor?.investor_name || '投資家を選択して判断根拠を確認してください。'}</p>
                </div>
                {selectedInvestor ? <span className="market-sim-investor-pill">{selectedInvestor.archetype}</span> : null}
              </div>
              {selectedInvestor && investorDecision ? (
                <>
                  <SimulationPersonaCard
                    badge={selectedInvestor.archetype.toUpperCase()}
                    badgeTone="investor"
                    name={selectedInvestor.persona?.display_name || selectedInvestor.investor_name}
                    subtitle={`${selectedInvestor.persona?.risk_posture || 'investor'} • ${selectedInvestor.persona?.preferred_price_band || formatCurrency(selectedInvestor.budget)}`}
                    traits={[
                      { label: '予算', value: formatCurrency(selectedInvestor.budget) },
                      { label: '残余資金', value: formatCurrency(selectedInvestor.cash_remaining) },
                      { label: '保有期間', value: `${selectedInvestor.hold_horizon_ticks}ティック` },
                      { label: '分散上限', value: selectedInvestor.diversification_cap },
                    ]}
                    summary={<p>{selectedInvestor.persona?.investment_thesis || investorDecision.chosen_action_reason}</p>}
                    lists={[
                      { label: 'Property Types', items: selectedInvestor.persona?.preferred_property_types || selectedInvestor.preferred_property_types },
                      { label: 'Neighborhood Preferences', items: selectedInvestor.persona?.neighborhood_preferences || [] },
                      { label: 'Avoidance Triggers', items: selectedInvestor.persona?.avoidance_triggers || [] },
                    ]}
                    footer={<p>出口戦略: {selectedInvestor.persona?.exit_style || '未設定'}</p>}
                  />

                  <div className="market-sim-decision-callout">
                    <div className="market-sim-target-row__header">
                      <strong>{investorDecision.property_address || 'No active property'}</strong>
                      <span className={`market-sim-action-pill market-sim-action-pill--${investorDecision.chosen_action}`}>{investorDecision.chosen_action}</span>
                    </div>
                    <p>{investorDecision.chosen_action_reason}</p>
                    <span>{investorDecision.entry_or_exit_reason}</span>
                  </div>

                  <div className="market-sim-inspector-grid">
                    <div>
                      <strong>選定理由</strong>
                      <ul className="market-sim-bullet-list">
                        {topDrivers.map((driver) => <li key={driver}>{driver}</li>)}
                      </ul>
                    </div>
                    <div>
                      <strong>主要リスク</strong>
                      <ul className="market-sim-bullet-list">
                        {riskNotes.map((note) => <li key={note}>{note}</li>)}
                      </ul>
                    </div>
                  </div>

                  <div>
                    <strong>前ティックからの変化</strong>
                    <ul className="market-sim-bullet-list">
                      {signalChanges.map((change) => <li key={change}>{change}</li>)}
                    </ul>
                  </div>

                  <div>
                    <strong>シグナル寄与度</strong>
                    <div className="market-sim-signal-list">
                      {Object.entries(investorDecision.signal_scores).map(([label, score]) => (
                        <SignalBar key={label} label={label} score={Number(score)} />
                      ))}
                    </div>
                  </div>

                  <div>
                    <strong>物件適合要因</strong>
                    <ul className="market-sim-bullet-list">
                      {investorDecision.property_match_factors.length > 0
                        ? investorDecision.property_match_factors.map((factor) => <li key={factor}>{factor}</li>)
                        : <li>このティックでは特別な適合要因は記録されていません。</li>}
                    </ul>
                  </div>

                  <div className="market-sim-stat-grid">
                    <StatRow label="残余資金" value={formatCurrency(Number(investorDecision.budget_position.cash_remaining || 0))} />
                    <StatRow label="売出価格" value={formatCurrency(Number(investorDecision.budget_position.asking_price || 0))} />
                    <StatRow label="余裕額" value={formatCurrency(Number(investorDecision.budget_position.headroom || 0))} />
                    <StatRow label="購入可能" value={String(investorDecision.budget_position.is_affordable ? 'はい' : 'いいえ')} />
                  </div>

                  <div>
                    <strong>次点物件（不採用）</strong>
                    <div className="market-sim-scroll-list market-sim-scroll-list--compact">
                      {investorDecision.rejected_alternatives.length > 0 ? investorDecision.rejected_alternatives.map((alternative, index) => (
                        <div key={`${String(alternative.property_id || alternative.address)}-${index}`} className="market-sim-alternative-card">
                          <strong>{String(alternative.address || alternative.property_id || 'Alternative')}</strong>
                          <span>Score {formatScore(Number(alternative.score || 0))} • Bias {String(alternative.action_bias || 'watch')}</span>
                          <p>{String(alternative.reason || 'It ranked below the chosen property on this tick.')}</p>
                        </div>
                      )) : <div className="market-sim-empty-copy">このティックでは候補物件は記録されていません。</div>}
                    </div>
                  </div>

                  <div>
                    <strong>行動履歴</strong>
                    <div className="market-sim-history-list">
                      {investorHistory.map((decision) => (
                        <button
                          key={`${decision.investor_id}-${decision.tick_num}`}
                          type="button"
                          className={`market-sim-history-item ${decision.tick_num - 1 === currentTickIndex ? 'is-active' : ''}`}
                          onClick={() => {
                            setCurrentTickIndex(decision.tick_num - 1)
                            setIsPlaying(false)
                            if (decision.property_id) setSelectedPropertyId(decision.property_id)
                          }}
                        >
                          <strong>Tick {decision.tick_num}</strong>
                          <span>{decision.chosen_action} • {decision.property_address || 'No property'}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <div className="market-sim-empty-copy">物件パネルから投資家を選択すると、各シグナルが判断にどう影響したか確認できます。</div>
              )}
            </section>
          </div>

          <section className="market-sim-surface">
            <div className="market-sim-section-heading">
              <div>
                <h3>取得結果</h3>
                <p>各取得が決定したティックに直接ジャンプできます。</p>
              </div>
            </div>
            <div className="market-sim-acquisition-grid">
              {result.acquisitions.map((acquisition) => (
                <button
                  key={acquisition.property_id}
                  type="button"
                  className="market-sim-acquisition-card"
                  onClick={() => {
                    const tickIndex = Math.max(0, acquisition.acquired_tick - 1)
                    setCurrentTickIndex(tickIndex)
                    setSelectedPropertyId(acquisition.property_id)
                    setSelectedInvestorId(acquisition.winning_investor_id)
                    setIsPlaying(false)
                  }}
                >
                  <strong>{acquisition.property_address}</strong>
                  <span>{acquisition.winning_investor_name}がティック{acquisition.acquired_tick}で取得</span>
                  <p>落札額 {formatCurrency(Number(acquisition.winning_bid))}</p>
                </button>
              ))}
              {result.acquisitions.length === 0 && (
                <div className="market-sim-empty-copy">今回のシミュレーションでは取得に至りませんでしたが、投資家の注目と入札の推移はリプレイで確認できます。</div>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="market-sim-metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function SignalBar({ label, score }: { label: string; score: number }) {
  return (
    <div className="market-sim-signal-bar">
      <div className="market-sim-signal-bar__header">
        <span>{label.replace(/_/g, ' ')}</span>
        <strong>{formatScore(score)}</strong>
      </div>
      <div className="market-sim-signal-bar__track">
        <div className="market-sim-signal-bar__fill" style={{ width: `${Math.max(0, Math.min(100, score * 100))}%` }} />
      </div>
    </div>
  )
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="market-sim-stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function deriveTopDrivers(decision: InvestorDecisionTrace | null) {
  if (!decision) return ['Select an investor decision to inspect drivers.']
  const ordered = Object.entries(decision.signal_scores)
    .filter(([label]) => label !== 'risk_penalty')
    .sort((left, right) => Number(right[1]) - Number(left[1]))
    .slice(0, 3)
    .map(([label, score]) => `${label.replace(/_/g, ' ')} contributed ${formatScore(Number(score))}.`)
  return ordered.length > 0 ? ordered : ['No positive drivers were recorded on this tick.']
}

function deriveRiskNotes(decision: InvestorDecisionTrace | null) {
  if (!decision) return ['Select an investor decision to inspect risks.']
  const riskPenalty = Number(decision.signal_scores.risk_penalty || 0)
  const notes = [`Risk penalty registered at ${formatScore(riskPenalty)}.`]
  if (riskPenalty >= 0.35) notes.push('Risk pressure was high enough to actively temper conviction.')
  if (decision.rejected_alternatives.length > 0) {
    notes.push(`The runner-up property still lost on risk-adjusted conviction versus ${decision.property_address || 'the chosen asset'}.`)
  }
  return notes
}

function deriveSignalChanges(current: InvestorDecisionTrace | null, previous: InvestorDecisionTrace | null) {
  if (!current) return ['Select an investor decision to compare signal movement.']
  if (!previous) return ['This is the first tick for the selected investor.']
  const changes = Object.entries(current.signal_scores)
    .map(([label, score]) => {
      const previousScore = Number(previous.signal_scores[label] || 0)
      const delta = Number(score) - previousScore
      return {
        label,
        delta,
      }
    })
    .filter((entry) => Math.abs(entry.delta) >= 0.02)
    .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))
    .slice(0, 3)
    .map((entry) => `${entry.label.replace(/_/g, ' ')} ${entry.delta > 0 ? 'rose' : 'fell'} by ${formatScore(Math.abs(entry.delta))}.`)
  return changes.length > 0 ? changes : ['No material signal changes were recorded versus the previous tick.']
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat('ja-JP', {
    style: 'currency',
    currency: 'JPY',
    maximumFractionDigits: 0,
  }).format(value)
}

function formatScore(score: number) {
  return score.toFixed(2)
}

function formatSignedCurrency(amount: number) {
  const rounded = Math.round(amount)
  if (rounded === 0) return '¥0'
  const prefix = rounded > 0 ? '+' : '-'
  return `${prefix}¥${Math.abs(rounded).toLocaleString()}`
}
