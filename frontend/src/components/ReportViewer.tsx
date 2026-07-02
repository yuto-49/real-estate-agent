import { useEffect, useState } from 'react'
import { api } from '../utils/api'

function formatYen(val: number | null | undefined): string {
  if (val == null) return '-'
  return '¥' + val.toLocaleString()
}

function formatPct(val: number): string {
  return (val >= 0 ? '+' : '') + val.toFixed(1) + '%'
}

interface SateiResult {
  session_id: string
  satei_price_yen: number
  confidence_low_yen: number
  confidence_high_yen: number
  comp_count: number
  method: string
  comps: Array<{
    comp_id: string
    address_hint: string | null
    raw_price_yen: number
    adjusted_price_yen: number
    menseki_m2: number | null
    built_year: number | null
    construction_type: string | null
    walk_minutes: number | null
    transaction_year: number | null
    transaction_quarter: number | null
    adjustments: Array<{ factor_name: string; adjustment_pct: number }>
    total_adjustment_pct: number
  }>
}

interface ProbPoint {
  asking_price_yen: number
  premium_pct: number
  p30: number
  p60: number
  p90: number
  p180: number
  expected_days: number
  expected_settlement_yen: number
}

interface ProbCurve {
  satei_price_yen: number
  points: ProbPoint[]
  sweet_spot_yen: number | null
  sweet_spot_pct: number | null
}

interface Props {
  reportId: string
  onComplete?: () => void
}

export default function ReportViewer({ reportId, onComplete }: Props) {
  const [satei, setSatei] = useState<SateiResult | null>(null)
  const [curve, setCurve] = useState<ProbCurve | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    void loadData()
  }, [reportId])

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.satei.get(reportId) as SateiResult
      setSatei(data)

      if (data.satei_price_yen > 0) {
        const probData = await api.priceProbability.compute({
          satei_price_yen: data.satei_price_yen,
        })
        setCurve(probData)
      }
      onComplete?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : '査定結果の取得に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <p>読み込み中...</p>
  if (error) return <p className="error">{error}</p>
  if (!satei) return <p>査定セッションが見つかりません</p>

  return (
    <div>
      {/* Satei Summary */}
      <div className="financial-section" style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ marginBottom: '0.75rem' }}>査定結果</h3>
        <div className="financial-grid">
          <div className="financial-metric">
            <span className="financial-metric-label">査定価格</span>
            <span className="financial-metric-value">{formatYen(satei.satei_price_yen)}</span>
          </div>
          <div className="financial-metric">
            <span className="financial-metric-label">信頼区間 (下限)</span>
            <span className="financial-metric-value">{formatYen(satei.confidence_low_yen)}</span>
          </div>
          <div className="financial-metric">
            <span className="financial-metric-label">信頼区間 (上限)</span>
            <span className="financial-metric-value">{formatYen(satei.confidence_high_yen)}</span>
          </div>
          <div className="financial-metric">
            <span className="financial-metric-label">取引事例数</span>
            <span className="financial-metric-value">{satei.comp_count}</span>
          </div>
        </div>
      </div>

      {/* Comp Grid */}
      {satei.comps.length > 0 && (
        <details className="report-section" open style={{ marginBottom: '1.5rem' }}>
          <summary>コンプグリッド ({satei.comps.length}件)</summary>
          <div className="report-section-content">
            <div className="report-list">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>所在地</th>
                    <th>取引価格</th>
                    <th>調整後価格</th>
                    <th>面積</th>
                    <th>築年</th>
                    <th>構造</th>
                    <th>駅徒歩</th>
                    <th>調整率</th>
                  </tr>
                </thead>
                <tbody>
                  {satei.comps.map((c) => (
                    <tr key={c.comp_id}>
                      <td>{c.address_hint || '-'}</td>
                      <td>{formatYen(c.raw_price_yen)}</td>
                      <td>{formatYen(c.adjusted_price_yen)}</td>
                      <td>{c.menseki_m2 != null ? `${c.menseki_m2}m²` : '-'}</td>
                      <td>{c.built_year ?? '-'}</td>
                      <td>{c.construction_type || '-'}</td>
                      <td>{c.walk_minutes != null ? `${c.walk_minutes}分` : '-'}</td>
                      <td>{formatPct(c.total_adjustment_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </details>
      )}

      {/* Price Probability Curve */}
      {curve && curve.points.length > 0 && (
        <details className="report-section" open>
          <summary>成約確率カーブ</summary>
          <div className="report-section-content">
            {curve.sweet_spot_yen && (
              <div className="financial-grid" style={{ marginBottom: '1rem' }}>
                <div className="financial-metric">
                  <span className="financial-metric-label">推奨売出価格 (Sweet Spot)</span>
                  <span className="financial-metric-value positive">{formatYen(curve.sweet_spot_yen)}</span>
                </div>
                <div className="financial-metric">
                  <span className="financial-metric-label">査定比</span>
                  <span className="financial-metric-value">{formatPct(curve.sweet_spot_pct ?? 0)}</span>
                </div>
              </div>
            )}

            <div className="report-list">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>売出価格</th>
                    <th>査定比</th>
                    <th>30日</th>
                    <th>60日</th>
                    <th>90日</th>
                    <th>180日</th>
                    <th>中央値日数</th>
                    <th>予想成約価格</th>
                  </tr>
                </thead>
                <tbody>
                  {curve.points.map((pt, i) => (
                    <tr key={i}>
                      <td>{formatYen(pt.asking_price_yen)}</td>
                      <td>{formatPct(pt.premium_pct)}</td>
                      <td>{(pt.p30 * 100).toFixed(0)}%</td>
                      <td>{(pt.p60 * 100).toFixed(0)}%</td>
                      <td>{(pt.p90 * 100).toFixed(0)}%</td>
                      <td>{(pt.p180 * 100).toFixed(0)}%</td>
                      <td>{pt.expected_days}日</td>
                      <td>{formatYen(pt.expected_settlement_yen)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </details>
      )}
    </div>
  )
}
