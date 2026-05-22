import type { ReactNode } from 'react'

interface PersonaTrait {
  label: string
  value: string | number
}

interface PersonaList {
  label: string
  items: string[]
}

interface SimulationPersonaCardProps {
  badge: string
  badgeTone?: 'buyer' | 'seller' | 'investor'
  name: string
  subtitle?: string
  summary?: ReactNode
  traits?: PersonaTrait[]
  lists?: PersonaList[]
  footer?: ReactNode
}

export default function SimulationPersonaCard({
  badge,
  badgeTone = 'investor',
  name,
  subtitle,
  summary,
  traits = [],
  lists = [],
  footer,
}: SimulationPersonaCardProps) {
  return (
    <article className="simulation-persona-card">
      <div className="simulation-persona-card__header">
        <span className={`simulation-persona-card__badge simulation-persona-card__badge--${badgeTone}`}>
          {badge}
        </span>
        <div className="simulation-persona-card__identity">
          <strong>{name}</strong>
          {subtitle ? <span>{subtitle}</span> : null}
        </div>
      </div>

      {traits.length > 0 ? (
        <div className="simulation-persona-card__traits">
          {traits.map((trait) => (
            <div key={trait.label} className="simulation-persona-card__trait">
              <span>{trait.label}</span>
              <strong>{trait.value}</strong>
            </div>
          ))}
        </div>
      ) : null}

      {summary ? <div className="simulation-persona-card__summary">{summary}</div> : null}

      {lists.length > 0 ? (
        <div className="simulation-persona-card__lists">
          {lists.map((list) => (
            <div key={list.label} className="simulation-persona-card__list">
              <span>{list.label}</span>
              <ul>
                {list.items.map((item, index) => <li key={`${list.label}-${index}`}>{item}</li>)}
              </ul>
            </div>
          ))}
        </div>
      ) : null}

      {footer ? <div className="simulation-persona-card__footer">{footer}</div> : null}
    </article>
  )
}
