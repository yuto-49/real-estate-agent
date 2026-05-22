import { useState } from 'react'
import { api } from '../../utils/api'
import type { UnderwriteRequest, UnderwriteResponse } from '../../utils/types'

const DEFAULT_INPUTS: UnderwriteRequest = {
  purchase_price: 300000,
  down_payment: 60000,
  loan_rate: 0.07,
  loan_term_years: 30,
  monthly_rent: 2400,
  vacancy_rate: 0.05,
  monthly_opex: 400,
  property_tax_annual: 3600,
  insurance_annual: 1200,
  closing_costs: 9000,
  rent_growth: 0.03,
  expense_growth: 0.025,
  appreciation: 0.03,
  exit_cap_rate: 0.07,
  selling_costs_pct: 0.06,
}

const FIELD_LABELS: Record<keyof UnderwriteRequest, string> = {
  purchase_price: 'Purchase price ($)',
  down_payment: 'Down payment ($)',
  loan_rate: 'Loan rate (decimal)',
  loan_term_years: 'Loan term (years)',
  monthly_rent: 'Monthly rent ($)',
  vacancy_rate: 'Vacancy rate (decimal)',
  monthly_opex: 'Monthly opex ($)',
  property_tax_annual: 'Property tax / yr ($)',
  insurance_annual: 'Insurance / yr ($)',
  closing_costs: 'Closing costs ($)',
  rent_growth: 'Rent growth (decimal)',
  expense_growth: 'Expense growth (decimal)',
  appreciation: 'Appreciation (decimal)',
  exit_cap_rate: 'Exit cap rate (decimal)',
  selling_costs_pct: 'Selling costs (decimal)',
}

export default function UnderwriteTab() {
  const [inputs, setInputs] = useState<UnderwriteRequest>(DEFAULT_INPUTS)
  const [result, setResult] = useState<UnderwriteResponse | null>(null)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)

  const run = async () => {
    setRunning(true)
    try {
      const res = await api.underwrite.run(inputs)
      setResult(res)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Underwrite failed')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="portfolio-tab" data-testid="underwrite-tab">
      {error && <p className="portfolio-error">{error}</p>}
      <section className="portfolio-form-grid portfolio-form-grid--wide">
        {(Object.keys(FIELD_LABELS) as Array<keyof UnderwriteRequest>).map((key) => (
          <label key={key}>
            {FIELD_LABELS[key]}
            <input
              type="number"
              value={inputs[key] ?? 0}
              onChange={(e) =>
                setInputs({ ...inputs, [key]: Number(e.target.value) })
              }
            />
          </label>
        ))}
      </section>
      <button type="button" onClick={() => void run()} disabled={running} data-testid="run-underwrite">
        {running ? 'Running…' : 'Run underwriting'}
      </button>

      {result && (
        <section className="portfolio-results" data-testid="underwrite-result">
          <div><span>Cap rate</span><strong>{(result.cap_rate * 100).toFixed(2)}%</strong></div>
          <div><span>Cash-on-cash</span><strong>{(result.cash_on_cash * 100).toFixed(2)}%</strong></div>
          <div><span>DSCR</span><strong>{result.dscr.toFixed(2)}</strong></div>
          <div><span>Annual NOI</span><strong>${Math.round(result.annual_noi).toLocaleString()}</strong></div>
          <div><span>Monthly PITI</span><strong>${Math.round(result.monthly_piti).toLocaleString()}</strong></div>
          <div><span>Breakeven occ.</span><strong>{(result.breakeven_occupancy * 100).toFixed(1)}%</strong></div>
          <div><span>5-yr IRR</span><strong>{result.irr_5yr != null ? `${(result.irr_5yr * 100).toFixed(2)}%` : '—'}</strong></div>
          <div><span>10-yr IRR</span><strong>{result.irr_10yr != null ? `${(result.irr_10yr * 100).toFixed(2)}%` : '—'}</strong></div>
        </section>
      )}
    </div>
  )
}
