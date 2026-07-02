interface ScoreGaugeProps {
  score: number
  label?: string
}

export default function ScoreGauge({ score, label = 'Overall Score' }: ScoreGaugeProps) {
  const tier = score >= 70 ? 'high' : score >= 45 ? 'mid' : 'low'
  return (
    <div className="ws-score-gauge">
      <div className={`ws-score-circle ws-score-circle--${tier}`}>{Math.round(score)}</div>
      <div className="ws-score-label">{label}</div>
    </div>
  )
}
