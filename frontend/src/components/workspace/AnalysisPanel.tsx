import ScoreGauge from './ScoreGauge'

interface Verdict {
  persona_key: string
  persona_title_ja: string
  payload: Record<string, unknown>
  error: string | null
}

interface AnalysisResult {
  listing_id: string
  overall_score: number
  summary: string
  verdicts: Verdict[]
}

interface AnalysisPanelProps {
  analysis: AnalysisResult | null
  loading: boolean
  error: string | null
}

function verdictClass(v: Verdict): string {
  const p = v.payload
  const verdict = p.verdict as string | undefined
  if (verdict === 'block') return 'ws-verdict--block'
  if (verdict === 'caution') return 'ws-verdict--caution'
  if (verdict === 'pass') return 'ws-verdict--pass'
  const score = (p.score as number) ?? (p.occupancy_forecast as number)
  if (typeof score === 'number') {
    const n = score <= 1 ? score * 100 : score
    if (n >= 70) return 'ws-verdict--pass'
    if (n >= 45) return 'ws-verdict--caution'
    return 'ws-verdict--block'
  }
  return ''
}

export default function AnalysisPanel({ analysis, loading, error }: AnalysisPanelProps) {
  return (
    <>
      <div className="workspace-panel-header">AI Analysis</div>

      {loading && (
        <div className="ws-loading">
          <div className="ws-spinner" />
          <span>Running analyst council (4 AI personas)...</span>
        </div>
      )}

      {error && (
        <div className="ws-card" style={{ borderColor: '#ef4444' }}>
          <div className="ws-card-title" style={{ color: '#ef4444' }}>Analysis Error</div>
          <p style={{ fontSize: 13, color: '#64748b' }}>{error}</p>
        </div>
      )}

      {!loading && !error && !analysis && (
        <div className="ws-empty">
          <div className="ws-empty-icon">🔍</div>
          <p>Select a property and click &quot;Analyze&quot; to see AI-powered risk assessment, location scoring, and investment thesis.</p>
        </div>
      )}

      {analysis && (
        <>
          <div className="ws-card">
            <ScoreGauge score={analysis.overall_score} />
          </div>

          <div className="ws-card">
            <div className="ws-card-title">Summary</div>
            <p style={{ fontSize: 13, color: '#475569', lineHeight: 1.5 }}>{analysis.summary}</p>
          </div>

          {analysis.verdicts.map((v) => (
            <div key={v.persona_key} className={`ws-verdict ${verdictClass(v)}`}>
              <div>
                <div className="ws-verdict-title">{v.persona_title_ja}</div>
                {v.error ? (
                  <div className="ws-verdict-summary" style={{ color: '#ef4444' }}>Error: {v.error}</div>
                ) : (
                  <div className="ws-verdict-summary">
                    {(v.payload.summary as string) ?? JSON.stringify(v.payload)}
                  </div>
                )}
                {v.payload.red_flags && Array.isArray(v.payload.red_flags) && (
                  <div style={{ marginTop: 6 }}>
                    {(v.payload.red_flags as Array<{ flag: string; severity: string }>).map((rf, i) => (
                      <span
                        key={i}
                        className={`ws-badge ws-badge--${rf.severity === 'high' ? 'red' : rf.severity === 'med' ? 'amber' : 'gray'}`}
                        style={{ marginRight: 4, marginBottom: 4 }}
                      >
                        {rf.flag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </>
      )}
    </>
  )
}
