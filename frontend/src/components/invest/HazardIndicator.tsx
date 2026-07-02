type HazardType = 'liquefaction' | 'flood' | 'landslide'

interface HazardIndicatorProps {
  type: HazardType
  score: number
}

const HAZARD_LABELS: Record<HazardType, string> = {
  liquefaction: 'Liquefaction',
  flood: 'Flood',
  landslide: 'Landslide',
}

function scoreToLevel(score: number): 'low' | 'moderate' | 'high' | 'unknown' {
  if (score < 0) return 'unknown'
  if (score <= 3) return 'low'
  if (score <= 6) return 'moderate'
  return 'high'
}

function levelLabel(level: string): string {
  if (level === 'low') return 'Low'
  if (level === 'moderate') return 'Mod'
  if (level === 'high') return 'High'
  return '\u2014'
}

export default function HazardIndicator({ type, score }: HazardIndicatorProps) {
  const level = scoreToLevel(score)
  return (
    <span className={`invest-hazard-badge level-${level}`} title={`${HAZARD_LABELS[type]}: ${score}/10`}>
      {HAZARD_LABELS[type]} {levelLabel(level)}
    </span>
  )
}

export type { HazardType }
