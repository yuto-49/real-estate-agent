import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../utils/api'

interface ReportSection {
  id: string
  title: string
  content: unknown
}

interface ReportStatus {
  id: string
  user_id: string
  status: string
  progress: number
  current_step: string
  step_key?: string
  created_at?: string
}

const WORKFLOW_STEPS = [
  { key: 'queued', label: 'Queued', icon: '1' },
  { key: 'loading_profile', label: 'Investor Profile', icon: '2' },
  { key: 'fetching_market', label: 'Market Data', icon: '3' },
  { key: 'enriching_listings', label: 'Enrich Listings', icon: '4' },
  { key: 'assembling_seed', label: 'Seed Document', icon: '5' },
  { key: 'running_simulation', label: 'Simulation', icon: '6' },
  { key: 'parsing_results', label: 'Parse Results', icon: '7' },
  { key: 'completed', label: 'Complete', icon: '8' },
]

const FINANCIAL_SECTIONS = new Set([
  'financial_analysis', 'monte_carlo_results', 'cash_flow_projections',
  'rent_vs_buy_analysis', 'tax_benefit_estimation', 'portfolio_metrics',
  'comparable_sales_analysis', 'neighborhood_scoring',
])

const SECTION_ORDER = [
  { key: 'market_outlook', title: 'Market Outlook' },
  { key: 'timing_recommendation', title: 'Timing Recommendation' },
  { key: 'financial_analysis', title: 'Financial Analysis' },
  { key: 'monte_carlo_results', title: 'Monte Carlo Simulation' },
  { key: 'cash_flow_projections', title: 'Cash Flow Projections' },
  { key: 'rent_vs_buy_analysis', title: 'Rent vs Buy Analysis' },
  { key: 'tax_benefit_estimation', title: 'Tax Benefits' },
  { key: 'portfolio_metrics', title: 'Portfolio Metrics' },
  { key: 'comparable_sales_analysis', title: 'Comparable Sales' },
  { key: 'neighborhood_scoring', title: 'Neighborhood Scores' },
  { key: 'strategy_comparison', title: 'Strategy Comparison' },
  { key: 'risk_assessment', title: 'Risk Assessment' },
  { key: 'property_recommendations', title: 'Property Recommendations' },
  { key: 'decision_anchors', title: 'Decision Anchors' },
]

function getActiveStepIndex(stepKey: string): number {
  const idx = WORKFLOW_STEPS.findIndex((s) => s.key === stepKey)
  return idx >= 0 ? idx : 0
}

function formatCurrency(val: number | string): string {
  const n = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(n)) return String(val)
  return '$' + n.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

function formatPct(val: number | string): string {
  const n = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(n)) return String(val)
  return n.toFixed(1) + '%'
}

interface Props {
  reportId: string
  onComplete?: () => void
}

export default function ReportViewer({ reportId, onComplete }: Props) {
  const [status, setStatus] = useState<ReportStatus | null>(null)
  const [reportJson, setReportJson] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState('')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const loadReport = useCallback(async (id: string) => {
    try {
      const data = await api.reports.get(id) as { report_json: Record<string, unknown>; status: string }
      setReportJson(data.report_json || {})
    } catch {
      // not ready yet
    }
  }, [])

  const pollStatus = useCallback(async (id: string) => {
    try {
      const data = await api.reports.status(id) as ReportStatus
      setStatus(data)
      if (data.status === 'completed') {
        stopPolling()
        await loadReport(id)
        onComplete?.()
      } else if (data.status === 'failed') {
        stopPolling()
        setError('Report generation failed.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to check status')
      stopPolling()
    }
  }, [stopPolling, loadReport, onComplete])

  useEffect(() => {
    void pollStatus(reportId)
    pollRef.current = setInterval(() => void pollStatus(reportId), 1500)
    return () => stopPolling()
  }, [reportId, pollStatus, stopPolling])

  const activeIdx = status ? getActiveStepIndex(
    status.step_key || status.current_step?.toLowerCase().replace(/\s+/g, '_') || 'queued'
  ) : 0

  const progress = status?.progress ?? 0
  const isRunning = status?.status === 'running' || status?.status === 'pending'
  const isCompleted = status?.status === 'completed'
  const isFailed = status?.status === 'failed'

  const sections: ReportSection[] = []
  if (reportJson) {
    for (const { key, title } of SECTION_ORDER) {
      if (reportJson[key] && Object.keys(reportJson[key] as object).length > 0) {
        sections.push({ id: key, title, content: reportJson[key] })
      }
    }
    for (const [key, val] of Object.entries(reportJson)) {
      if (key === 'simulation_metadata') continue
      if (!SECTION_ORDER.some(s => s.key === key) && val && typeof val === 'object' && Object.keys(val as object).length > 0) {
        sections.push({
          id: key,
          title: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
          content: val,
        })
      }
    }
  }

  return (
    <div>
      {/* Workflow Progress */}
      <div className="workflow-container">
        <div className="workflow-progress-bar">
          <div
            className={`workflow-progress-fill ${isCompleted ? 'complete' : isFailed ? 'failed' : ''}`}
            style={{ width: `${progress}%` }}
          />
          <span className="workflow-progress-label">{progress}%</span>
        </div>

        {status?.current_step && (
          <div className="workflow-current-step">
            {isRunning && <span className="workflow-spinner" />}
            {status.current_step}
          </div>
        )}

        <div className="workflow-steps">
          {WORKFLOW_STEPS.map((step, idx) => {
            const isDone = idx < activeIdx || isCompleted
            const isActive = idx === activeIdx && isRunning
            let cls = 'workflow-step'
            if (isDone) cls += ' done'
            if (isActive) cls += ' active'
            if (isFailed && idx === activeIdx) cls += ' failed'
            return (
              <div key={step.key} className={cls}>
                <div className="workflow-step-connector">
                  {idx > 0 && <div className={`connector-line ${isDone ? 'done' : ''}`} />}
                </div>
                <div className="workflow-step-circle">
                  {isDone ? (
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M2.5 7L5.5 10L11.5 4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  ) : (
                    <span>{step.icon}</span>
                  )}
                </div>
                <div className="workflow-step-label">{step.label}</div>
              </div>
            )
          })}
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {/* Report Sections */}
      {isCompleted && sections.length > 0 && (
        <div className="report-sections">
          {sections.map((section) => (
            <details key={section.id} className="report-section" open>
              <summary>{section.title}</summary>
              <div className="report-section-content">
                {FINANCIAL_SECTIONS.has(section.id)
                  ? renderFinancialSection(section)
                  : renderSectionContent(section)
                }
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  )
}


// ── Financial Section Renderers (extracted from ReportPage) ──

function renderFinancialSection(section: ReportSection) {
  const data = section.content as Record<string, unknown>
  switch (section.id) {
    case 'financial_analysis': return renderFinancialAnalysis(data)
    case 'monte_carlo_results': return renderMonteCarlo(data)
    case 'neighborhood_scoring': return renderNeighborhoodScoring(data)
    case 'portfolio_metrics': return renderPortfolioMetrics(data)
    case 'rent_vs_buy_analysis': return renderRentVsBuy(data)
    case 'tax_benefit_estimation': return renderTaxBenefits(data)
    case 'comparable_sales_analysis': return renderComparableSales(data)
    case 'cash_flow_projections': return renderCashFlowProjections(data)
    default: return renderSectionContent(section)
  }
}

function renderFinancialAnalysis(data: Record<string, unknown>) {
  const mortgage = (data.mortgage || {}) as Record<string, unknown>
  const cashFlow = (data.cash_flow || {}) as Record<string, unknown>
  return (
    <div className="financial-section">
      <div className="financial-grid">
        <div className="financial-metric"><span className="financial-metric-label">Property Value</span><span className="financial-metric-value">{formatCurrency(data.property_value as number)}</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Down Payment</span><span className="financial-metric-value">{formatPct(((data.down_payment_pct as number) || 0) * 100)}</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Loan Amount</span><span className="financial-metric-value">{formatCurrency(data.loan_amount as number)}</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Monthly Payment</span><span className="financial-metric-value">{formatCurrency(mortgage.monthly_payment as number)}</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Interest Rate</span><span className="financial-metric-value">{String(mortgage.annual_rate_pct)}%</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Total Interest</span><span className="financial-metric-value">{formatCurrency(mortgage.total_interest as number)}</span></div>
      </div>
      {cashFlow && typeof cashFlow.net_cash_flow === 'number' && (
        <div className="financial-grid">
          <div className="financial-metric"><span className="financial-metric-label">Monthly Net Cash Flow</span><span className={`financial-metric-value ${(cashFlow.net_cash_flow as number) >= 0 ? 'positive' : 'negative'}`}>{formatCurrency(cashFlow.net_cash_flow as number)}</span></div>
          <div className="financial-metric"><span className="financial-metric-label">Gross Rental Income</span><span className="financial-metric-value">{formatCurrency(cashFlow.gross_rental_income as number)}</span></div>
          <div className="financial-metric"><span className="financial-metric-label">Total Expenses</span><span className="financial-metric-value">{formatCurrency(cashFlow.total_expenses as number)}</span></div>
        </div>
      )}
    </div>
  )
}

function renderMonteCarlo(data: Record<string, unknown>) {
  const irr = (data.irr_distribution || {}) as Record<string, number>
  const npv = (data.npv_distribution || {}) as Record<string, number>
  const maxIrr = Math.max(Math.abs(irr.p10 || 0), Math.abs(irr.p90 || 20))
  return (
    <div className="financial-section">
      <div className="financial-grid">
        <div className="financial-metric"><span className="financial-metric-label">Scenarios Run</span><span className="financial-metric-value">{String(data.scenarios_run)}</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Probability of Loss</span><span className={`financial-metric-value ${(data.probability_of_loss as number) > 0.2 ? 'negative' : 'positive'}`}>{formatPct(((data.probability_of_loss as number) || 0) * 100)}</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Mean IRR</span><span className="financial-metric-value">{formatPct(data.mean_irr as number)}</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Mean NPV</span><span className="financial-metric-value">{formatCurrency(data.mean_npv as number)}</span></div>
      </div>
      {Object.keys(irr).length > 0 && (
        <>
          <h4 style={{ margin: '0.75rem 0 0.5rem', fontSize: '0.88rem', color: '#555' }}>IRR Distribution</h4>
          {['p10', 'p25', 'p50', 'p75', 'p90'].map(p => (
            <div key={p} className="percentile-bar">
              <span className="percentile-bar-label">{p.toUpperCase()}</span>
              <div className="percentile-bar-track"><div className="percentile-bar-fill" style={{ width: `${Math.max(0, ((irr[p] || 0) / (maxIrr || 1)) * 50 + 50)}%` }} /></div>
              <span className="percentile-bar-value">{formatPct(irr[p] || 0)}</span>
            </div>
          ))}
        </>
      )}
      {Object.keys(npv).length > 0 && (
        <>
          <h4 style={{ margin: '0.75rem 0 0.5rem', fontSize: '0.88rem', color: '#555' }}>NPV Distribution</h4>
          {['p10', 'p25', 'p50', 'p75', 'p90'].map(p => (
            <div key={p} className="percentile-bar">
              <span className="percentile-bar-label">{p.toUpperCase()}</span>
              <div className="percentile-bar-track"><div className="percentile-bar-fill" style={{ width: `${Math.min(100, Math.max(0, ((npv[p] || 0) + 50000) / 3000))}%` }} /></div>
              <span className="percentile-bar-value">{formatCurrency(npv[p] || 0)}</span>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

function renderNeighborhoodScoring(data: Record<string, unknown>) {
  const overall = data.overall_score as number
  const categories = Object.entries(data).filter(([k]) => k !== 'overall_score')
  return (
    <div className="financial-section">
      <div className="financial-metric" style={{ marginBottom: '1rem', maxWidth: '200px' }}>
        <span className="financial-metric-label">Overall Score</span>
        <span className="financial-metric-value">{Math.round(overall)} / 100</span>
      </div>
      {categories.map(([key, val]) => {
        const score = val as number
        const level = score >= 75 ? 'high' : score >= 55 ? 'medium' : 'low'
        return (
          <div key={key} className="score-bar">
            <span className="score-bar-label">{key.replace(/_/g, ' ')}</span>
            <div className="score-bar-track"><div className={`score-bar-fill ${level}`} style={{ width: `${score}%` }} /></div>
            <span className="score-bar-value">{score}</span>
          </div>
        )
      })}
    </div>
  )
}

function renderPortfolioMetrics(data: Record<string, unknown>) {
  return (
    <div className="financial-section">
      <div className="financial-grid">
        {Object.entries(data).map(([key, val]) => (
          <div key={key} className="financial-metric">
            <span className="financial-metric-label">{key.replace(/_/g, ' ')}</span>
            <span className="financial-metric-value">{key.includes('pct') || key.includes('ratio') ? formatPct(val as number) : String(val)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function renderRentVsBuy(data: Record<string, unknown>) {
  const scenarios = (data.scenarios || {}) as Record<string, Record<string, string>>
  return (
    <div className="financial-section">
      <div className="financial-grid">
        <div className="financial-metric"><span className="financial-metric-label">Break-Even</span><span className="financial-metric-value">{String(data.break_even_months)} months</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Monthly Cost to Own</span><span className="financial-metric-value">{formatCurrency(data.monthly_cost_to_own as number)}</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Comparable Rent</span><span className="financial-metric-value">{formatCurrency(data.comparable_monthly_rent as number)}</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Upfront Costs</span><span className="financial-metric-value">{formatCurrency(data.upfront_costs as number)}</span></div>
      </div>
      {Object.keys(scenarios).length > 0 && (
        <div style={{ marginTop: '0.75rem' }}>
          <h4 style={{ fontSize: '0.88rem', color: '#555', marginBottom: '0.5rem' }}>Scenario Advantages</h4>
          <div className="report-cards">
            {Object.entries(scenarios).map(([name, vals]) => (
              <div key={name} className="report-card">
                <div className="report-card-field"><span className="report-card-label">Scenario</span><span className="report-card-value" style={{ textTransform: 'capitalize', fontWeight: 600 }}>{name}</span></div>
                {Object.entries(vals).map(([k, v]) => (
                  <div key={k} className="report-card-field"><span className="report-card-label">{k.replace(/_/g, ' ')}</span><span className="report-card-value" style={{ textTransform: 'capitalize' }}>{v}</span></div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function renderTaxBenefits(data: Record<string, unknown>) {
  const income = (data.income_tax || {}) as Record<string, unknown>
  const depreciation = (data.depreciation || {}) as Record<string, unknown>
  return (
    <div className="financial-section">
      <div className="financial-grid">
        <div className="financial-metric"><span className="financial-metric-label">Total Annual Tax Savings</span><span className="financial-metric-value positive">{formatCurrency(data.total_annual_tax_savings as number)}</span></div>
        {income.estimated_annual_savings != null && <div className="financial-metric"><span className="financial-metric-label">Income Tax Savings</span><span className="financial-metric-value">{formatCurrency(income.estimated_annual_savings as number)}</span></div>}
        {depreciation.annual_tax_savings != null && <div className="financial-metric"><span className="financial-metric-label">Depreciation Tax Savings</span><span className="financial-metric-value">{formatCurrency(depreciation.annual_tax_savings as number)}</span></div>}
        {income.mortgage_interest_deduction != null && <div className="financial-metric"><span className="financial-metric-label">Mortgage Interest Deduction</span><span className="financial-metric-value">{formatCurrency(income.mortgage_interest_deduction as number)}</span></div>}
      </div>
    </div>
  )
}

function renderComparableSales(data: Record<string, unknown>) {
  const comps = (data.comparables || []) as Array<Record<string, unknown>>
  return (
    <div className="financial-section">
      <div className="financial-grid">
        <div className="financial-metric"><span className="financial-metric-label">Subject Price/SqFt</span><span className="financial-metric-value">{formatCurrency(data.subject_price_per_sqft as number)}</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Median Price/SqFt</span><span className="financial-metric-value">{formatCurrency(data.median_price_per_sqft as number)}</span></div>
        <div className="financial-metric"><span className="financial-metric-label">Value Indicator</span><span className={`financial-metric-value ${(data.value_indicator as string) === 'below_market' ? 'positive' : (data.value_indicator as string) === 'above_market' ? 'negative' : ''}`}>{(data.value_indicator as string || '').replace(/_/g, ' ')}</span></div>
      </div>
      {comps.length > 0 && (
        <div className="report-cards" style={{ marginTop: '0.75rem' }}>
          {comps.slice(0, 5).map((comp, i) => (
            <div key={i} className="report-card">
              <div className="report-card-field"><span className="report-card-label">Address</span><span className="report-card-value">{comp.address as string}</span></div>
              <div className="report-card-field"><span className="report-card-label">Sale Price</span><span className="report-card-value">{formatCurrency(comp.sale_price as number)}</span></div>
              <div className="report-card-field"><span className="report-card-label">Price/SqFt</span><span className="report-card-value">{formatCurrency(comp.price_per_sqft as number)}</span></div>
              <div className="report-card-field"><span className="report-card-label">Days on Market</span><span className="report-card-value">{comp.days_on_market as number}</span></div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function renderCashFlowProjections(data: Record<string, unknown>) {
  const scenarios = Object.entries(data) as [string, Record<string, Record<string, unknown>>][]
  return (
    <div className="financial-section">
      {scenarios.map(([name, horizons]) => (
        <div key={name} style={{ marginBottom: '1rem' }}>
          <h4 style={{ fontSize: '0.88rem', color: '#555', marginBottom: '0.5rem', textTransform: 'capitalize' }}>{name} Scenario</h4>
          <div className="report-cards">
            {Object.entries(horizons).map(([horizon, vals]) => (
              <div key={horizon} className="report-card">
                <div className="report-card-field"><span className="report-card-label">Horizon</span><span className="report-card-value" style={{ fontWeight: 600 }}>{horizon.replace(/_/g, ' ')}</span></div>
                {Object.entries(vals).map(([k, v]) => (
                  <div key={k} className="report-card-field"><span className="report-card-label">{k.replace(/_/g, ' ')}</span><span className="report-card-value">{typeof v === 'number' ? formatCurrency(v) : String(v)}</span></div>
                ))}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function renderSectionContent(section: ReportSection) {
  const content = section.content
  if (Array.isArray(content)) {
    return (
      <div className="report-cards">
        {content.map((item, i) => (
          <div key={i} className="report-card">
            {typeof item === 'object' && item !== null
              ? Object.entries(item as Record<string, unknown>).map(([k, v]) => (
                <div key={k} className="report-card-field">
                  <span className="report-card-label">{k.replace(/_/g, ' ')}</span>
                  <span className="report-card-value">{Array.isArray(v) ? v.join(', ') : String(v)}</span>
                </div>
              ))
              : <span>{String(item)}</span>
            }
          </div>
        ))}
      </div>
    )
  }
  if (typeof content === 'object' && content !== null) {
    return (
      <div className="report-kv">
        {Object.entries(content as Record<string, unknown>).map(([k, v]) => (
          <div key={k} className="report-kv-row">
            <span className="report-kv-key">{k.replace(/_/g, ' ')}</span>
            <span className="report-kv-val">{typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)}</span>
          </div>
        ))}
      </div>
    )
  }
  return <pre>{JSON.stringify(content, null, 2)}</pre>
}
