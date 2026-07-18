import { useState } from 'react'
import { api } from '../../utils/api'
import { formatJpyCompact } from '../../utils/japan'
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
  purchase_price: '取得価格（円）',
  down_payment: '自己資金（円）',
  loan_rate: '借入金利',
  loan_term_years: '返済年数',
  monthly_rent: '月額賃料（円）',
  vacancy_rate: '空室率',
  monthly_opex: '月次運営費（円）',
  property_tax_annual: '固定資産税（年額）',
  insurance_annual: '保険料（年額）',
  closing_costs: '取得諸費用（円）',
  rent_growth: '賃料成長率',
  expense_growth: '費用成長率',
  appreciation: '価格上昇率',
  exit_cap_rate: '出口利回り',
  selling_costs_pct: '売却コスト率',
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
      setError(err instanceof Error ? err.message : '収支試算に失敗しました。')
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
        {running ? '計算中…' : '収支試算を実行'}
      </button>

      {result && (
        <section className="portfolio-results" data-testid="underwrite-result">
          <div><span>表面利回り</span><strong>{(result.cap_rate * 100).toFixed(2)}%</strong></div>
          <div><span>自己資金利回り</span><strong>{(result.cash_on_cash * 100).toFixed(2)}%</strong></div>
          <div><span>DSCR</span><strong>{result.dscr.toFixed(2)}</strong></div>
          <div><span>年間NOI</span><strong>{formatJpyCompact(result.annual_noi)}</strong></div>
          <div><span>月次返済総額</span><strong>{formatJpyCompact(result.monthly_piti)}</strong></div>
          <div><span>損益分岐稼働率</span><strong>{(result.breakeven_occupancy * 100).toFixed(1)}%</strong></div>
          <div><span>5年IRR</span><strong>{result.irr_5yr != null ? `${(result.irr_5yr * 100).toFixed(2)}%` : '—'}</strong></div>
          <div><span>10年IRR</span><strong>{result.irr_10yr != null ? `${(result.irr_10yr * 100).toFixed(2)}%` : '—'}</strong></div>
        </section>
      )}
    </div>
  )
}
