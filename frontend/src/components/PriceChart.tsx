interface PricePoint {
  round: number
  role: string
  price: number
}

interface ScenarioPath {
  scenario: string
  price_path: PricePoint[]
}

interface Props {
  scenarioPaths: ScenarioPath[]
  askingPrice?: number
}

const SCENARIO_COLORS = [
  '#1d4ed8', '#b45309', '#7c3aed', '#15803d', '#dc2626', '#0891b2',
]

export default function PriceChart({ scenarioPaths, askingPrice }: Props) {
  if (scenarioPaths.length === 0) return null

  const allPrices = scenarioPaths.flatMap(s => s.price_path.map(p => p.price))
  if (askingPrice) allPrices.push(askingPrice)
  const minPrice = Math.min(...allPrices) * 0.98
  const maxPrice = Math.max(...allPrices) * 1.02
  const maxRound = Math.max(...scenarioPaths.flatMap(s => s.price_path.map(p => p.round)), 1)

  const width = 700
  const height = 300
  const padL = 80
  const padR = 20
  const padT = 20
  const padB = 40
  const chartW = width - padL - padR
  const chartH = height - padT - padB

  const scaleX = (round: number) => padL + (round / maxRound) * chartW
  const scaleY = (price: number) => padT + chartH - ((price - minPrice) / (maxPrice - minPrice)) * chartH

  const formatK = (v: number) => v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v.toLocaleString()}`

  // Y-axis ticks
  const yTicks: number[] = []
  const step = Math.ceil((maxPrice - minPrice) / 5 / 1000) * 1000
  for (let v = Math.floor(minPrice / step) * step; v <= maxPrice; v += step) {
    if (v >= minPrice) yTicks.push(v)
  }

  return (
    <div className="price-chart">
      <h4>Price Convergence</h4>
      <svg viewBox={`0 0 ${width} ${height}`} className="price-chart-svg">
        {/* Grid */}
        {yTicks.map((v) => (
          <g key={v}>
            <line x1={padL} y1={scaleY(v)} x2={width - padR} y2={scaleY(v)} stroke="#f0f0f0" strokeWidth="1" />
            <text x={padL - 8} y={scaleY(v) + 4} textAnchor="end" fontSize="11" fill="#888">{formatK(v)}</text>
          </g>
        ))}

        {/* X-axis labels */}
        {Array.from({ length: Math.min(maxRound, 10) }, (_, i) => {
          const r = Math.round((i + 1) * maxRound / Math.min(maxRound, 10))
          return (
            <text key={r} x={scaleX(r)} y={height - 8} textAnchor="middle" fontSize="11" fill="#888">R{r}</text>
          )
        })}

        {/* Asking price line */}
        {askingPrice && (
          <>
            <line x1={padL} y1={scaleY(askingPrice)} x2={width - padR} y2={scaleY(askingPrice)} stroke="#999" strokeWidth="1" strokeDasharray="4 3" />
            <text x={width - padR + 2} y={scaleY(askingPrice) + 4} fontSize="10" fill="#999">Ask</text>
          </>
        )}

        {/* Scenario paths */}
        {scenarioPaths.map((sp, idx) => {
          const color = SCENARIO_COLORS[idx % SCENARIO_COLORS.length]
          const sorted = [...sp.price_path].sort((a, b) => a.round - b.round)
          if (sorted.length < 2) return null

          const d = sorted.map((p, i) =>
            `${i === 0 ? 'M' : 'L'} ${scaleX(p.round)} ${scaleY(p.price)}`
          ).join(' ')

          return (
            <g key={sp.scenario}>
              <path d={d} fill="none" stroke={color} strokeWidth="2" opacity="0.8" />
              {sorted.map((p, i) => (
                <circle
                  key={i}
                  cx={scaleX(p.round)}
                  cy={scaleY(p.price)}
                  r="3"
                  fill={color}
                  opacity="0.9"
                />
              ))}
            </g>
          )
        })}
      </svg>

      {/* Legend */}
      <div className="price-chart-legend">
        {scenarioPaths.map((sp, idx) => (
          <div key={sp.scenario} className="price-chart-legend-item">
            <span
              className="price-chart-legend-dot"
              style={{ background: SCENARIO_COLORS[idx % SCENARIO_COLORS.length] }}
            />
            <span>{sp.scenario.replace(/_/g, ' ')}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
