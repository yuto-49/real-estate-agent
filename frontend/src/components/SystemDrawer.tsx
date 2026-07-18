import { useEffect, useState } from 'react'
import { api } from '../utils/api'

interface SystemHealth {
  status: string
  version: string
}

interface SystemMetrics {
  counters: Record<string, number>
  gauges: Record<string, number>
  histograms: Record<string, Record<string, number>>
}

interface Props {
  open: boolean
  onClose: () => void
}

export default function SystemDrawer({ open, onClose }: Props) {
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) void loadSystem()
  }, [open])

  const loadSystem = async () => {
    setLoading(true)
    setError('')
    try {
      const [healthData, metricsData] = await Promise.all([
        api.system.health(),
        api.system.metrics(),
      ])
      setHealth(healthData)
      setMetrics(metricsData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'システム情報を取得できませんでした。')
    } finally {
      setLoading(false)
    }
  }

  if (!open) return null

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel drawer-right" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <h3>システム状態</h3>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="secondary-btn" onClick={() => void loadSystem()} disabled={loading}>再読み込み</button>
            <button className="drawer-close-btn" onClick={onClose}>x</button>
          </div>
        </div>

        <div className="drawer-body">
          {loading && <p>システム状態を読み込み中…</p>}
          {error && <p className="error">{error}</p>}

          {health && metrics && (
            <>
              <div className="system-grid">
                <article className="system-card">
                  <h3>状態</h3>
                  <p className={`status-pill ${health.status === 'ok' ? 'ok' : 'error'}`}>
                    {health.status}
                  </p>
                </article>
                <article className="system-card">
                  <h3>バージョン</h3>
                  <p>{health.version}</p>
                </article>
                <article className="system-card">
                  <h3>カウンター</h3>
                  <p>{Object.keys(metrics.counters).length}</p>
                </article>
                <article className="system-card">
                  <h3>ゲージ</h3>
                  <p>{Object.keys(metrics.gauges).length}</p>
                </article>
                <article className="system-card">
                  <h3>ヒストグラム</h3>
                  <p>{Object.keys(metrics.histograms).length}</p>
                </article>
              </div>
              <div className="system-metrics-raw">
                <h3>メトリクス（JSON）</h3>
                <pre>{JSON.stringify(metrics, null, 2)}</pre>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
