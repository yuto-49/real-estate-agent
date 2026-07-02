import { useState } from 'react'
import { api } from '../../utils/api'
import type { UnderwriteRequest, UnderwriteResponse } from '../../utils/types'

const DEFAULT_INPUTS: UnderwriteRequest = {
  purchase_price: 35000000,
  down_payment: 3500000,
  loan_rate: 0.018,
  loan_term_years: 35,
  monthly_rent: 95000,
  vacancy_rate: 0.05,
  monthly_opex: 15000,
  property_tax_annual: 80000,
  insurance_annual: 15000,
  closing_costs: 2450000,
  rent_growth: 0.005,
  expense_growth: 0.01,
  appreciation: 0.01,
  exit_cap_rate: 0.05,
  selling_costs_pct: 0.04,
}

const FIELD_LABELS: Record<keyof UnderwriteRequest, string> = {
  purchase_price: '購入価格（円）',
  down_payment: '頭金（円）',
  loan_rate: '借入金利（小数）',
  loan_term_years: '借入期間（年）',
  monthly_rent: '月額賃料（円）',
  vacancy_rate: '空室率（小数）',
  monthly_opex: '月額経費（管理費+修繕積立金）（円）',
  property_tax_annual: '固定資産税・都市計画税（年額・円）',
  insurance_annual: '火災保険料（年額・円）',
  closing_costs: '取得時諸費用（円）',
  rent_growth: '賃料上昇率（小数）',
  expense_growth: '経費上昇率（小数）',
  appreciation: '不動産価格上昇率（小数）',
  exit_cap_rate: '出口キャップレート（小数）',
  selling_costs_pct: '売却時諸費用率（小数）',
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
        {running ? '計算中…' : '収支シミュレーション実行'}
      </button>

      {result && (
        <section className="portfolio-results" data-testid="underwrite-result">
          <div><span>表面利回り</span><strong>{(result.cap_rate * 100).toFixed(2)}%</strong></div>
          <div><span>自己資金利回り（CCR）</span><strong>{(result.cash_on_cash * 100).toFixed(2)}%</strong></div>
          <div><span>DSCR（返済余裕率）</span><strong>{result.dscr.toFixed(2)}</strong></div>
          <div><span>年間NOI（純収益）</span><strong>¥{Math.round(result.annual_noi).toLocaleString()}</strong></div>
          <div><span>月額返済額</span><strong>¥{Math.round(result.monthly_piti).toLocaleString()}</strong></div>
          <div><span>損益分岐稼働率</span><strong>{(result.breakeven_occupancy * 100).toFixed(1)}%</strong></div>
          <div><span>5年IRR</span><strong>{result.irr_5yr != null ? `${(result.irr_5yr * 100).toFixed(2)}%` : '—'}</strong></div>
          <div><span>10年IRR</span><strong>{result.irr_10yr != null ? `${(result.irr_10yr * 100).toFixed(2)}%` : '—'}</strong></div>
        </section>
      )}
    </div>
  )
}
