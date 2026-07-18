import { useState } from 'react'
import { api } from '../../utils/api'
import type {
  SliderRange,
  StressTestConfig,
  StressTestResponse,
  UnderwriteRequest,
} from '../../utils/types'

const BASE_INPUTS: UnderwriteRequest = {
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
  exit_cap_rate: 0.07,
}

type SliderKey = 'vacancy_rate' | 'rent_growth' | 'expense_growth' | 'loan_rate' | 'exit_cap_rate'

const SLIDER_DEFAULTS: Record<SliderKey, SliderRange> = {
  vacancy_rate: { low: 0.03, high: 0.12 },
  rent_growth: { low: 0.0, high: 0.04 },
  expense_growth: { low: 0.02, high: 0.04 },
  loan_rate: { low: 0.05, high: 0.08 },
  exit_cap_rate: { low: 0.06, high: 0.085 },
}

const SLIDER_LABELS: Record<SliderKey, string> = {
  vacancy_rate: '空室率',
  rent_growth: '賃料成長率',
  expense_growth: '費用成長率',
  loan_rate: '借入金利',
  exit_cap_rate: '出口利回り',
}

export default function StressTestTab() {
  const [iterations, setIterations] = useState(5000)
  const [sliders, setSliders] = useState<Record<SliderKey, SliderRange>>(SLIDER_DEFAULTS)
  const [result, setResult] = useState<StressTestResponse | null>(null)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)

  const updateSlider = (key: SliderKey, bound: keyof SliderRange, value: number) => {
    setSliders((prev) => ({ ...prev, [key]: { ...prev[key], [bound]: value } }))
  }

  const run = async () => {
    setRunning(true)
    try {
      const config: StressTestConfig = { iterations, ...sliders }
      const res = await api.underwrite.stressTest({ base_inputs: BASE_INPUTS, config })
      setResult(res)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ストレステストに失敗しました。')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="portfolio-tab" data-testid="stress-test-tab">
      {error && <p className="portfolio-error">{error}</p>}

      <label className="stress-iterations">
        モンテカルロ試行回数
        <input
          type="number"
          min={10}
          max={20000}
          value={iterations}
          onChange={(e) => setIterations(Number(e.target.value))}
        />
      </label>

      <section className="stress-sliders">
        {(Object.keys(SLIDER_LABELS) as SliderKey[]).map((key) => (
          <div key={key} className="stress-slider-row">
            <span>{SLIDER_LABELS[key]}</span>
            <label>
              下限
              <input
                type="number"
                step="0.005"
                value={sliders[key].low}
                onChange={(e) => updateSlider(key, 'low', Number(e.target.value))}
              />
            </label>
            <label>
              上限
              <input
                type="number"
                step="0.005"
                value={sliders[key].high}
                onChange={(e) => updateSlider(key, 'high', Number(e.target.value))}
              />
            </label>
          </div>
        ))}
      </section>

      <button type="button" onClick={() => void run()} disabled={running} data-testid="run-stress-test">
        {running ? '試算中…' : 'ストレステストを実行'}
      </button>

      {result && (
        <section className="portfolio-results" data-testid="stress-test-result">
          <div><span>試行回数</span><strong>{result.iterations.toLocaleString()}</strong></div>
          <div>
            <span>利回り P10 / P50 / P90</span>
            <strong>
              {(result.cap_rate_p10 * 100).toFixed(1)}% / {(result.cap_rate_p50 * 100).toFixed(1)}% /{' '}
              {(result.cap_rate_p90 * 100).toFixed(1)}%
            </strong>
          </div>
          <div>
            <span>DSCR P10 / P50 / P90</span>
            <strong>
              {result.dscr_p10.toFixed(2)} / {result.dscr_p50.toFixed(2)} / {result.dscr_p90.toFixed(2)}
            </strong>
          </div>
          <div>
            <span>赤字CF確率</span>
            <strong>{(result.probability_negative_cash_flow * 100).toFixed(1)}%</strong>
          </div>
          <div>
            <span>DSCR&lt;1 の確率</span>
            <strong>{(result.probability_dscr_under_1 * 100).toFixed(1)}%</strong>
          </div>
        </section>
      )}
    </div>
  )
}
