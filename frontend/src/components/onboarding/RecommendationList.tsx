import { useEffect, useState } from 'react'

import { useAuth } from '../../hooks/useAuth'
import { api } from '../../utils/api'
import type {
  InvestorProfileDraft,
} from '../../pages/OnboardingWizard'
import type { PropertyRecommendation } from '../../utils/types'

interface RecommendationListProps {
  profile: InvestorProfileDraft
  onSelect: (propertyId: string) => void
}

interface FetchState {
  loading: boolean
  error: string | null
  recommendations: PropertyRecommendation[]
  candidatesConsidered: number | null
}

const INITIAL: FetchState = {
  loading: true,
  error: null,
  recommendations: [],
  candidatesConsidered: null,
}

export default function RecommendationList({
  profile,
  onSelect,
}: RecommendationListProps) {
  const { user } = useAuth()
  const [state, setState] = useState<FetchState>(INITIAL)

  useEffect(() => {
    if (!user?.id) {
      setState({
        loading: false,
        error: 'Sign in to see your recommendations.',
        recommendations: [],
        candidatesConsidered: null,
      })
      return
    }

    let cancelled = false
    setState(INITIAL)
    void api.recommendations
      .list(user.id, 10)
      .then((res) => {
        if (cancelled) return
        setState({
          loading: false,
          error: null,
          recommendations: res.recommendations,
          candidatesConsidered: res.candidates_considered,
        })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setState({
          loading: false,
          error:
            err instanceof Error ? err.message : 'Could not load recommendations.',
          recommendations: [],
          candidatesConsidered: null,
        })
      })

    return () => {
      cancelled = true
    }
  }, [user?.id])

  return (
    <div className="onboarding-recommendations" data-testid="onboarding-recommendations">
      <h3>Suggested properties</h3>
      <p className="onboarding-subtle">
        Budget ¥{profile.budget?.toLocaleString() ?? '—'} · Strategy{' '}
        {profile.strategy ?? '—'} · Cap rate target{' '}
        {profile.target_cap_rate ?? '—'}%
      </p>

      {state.loading && (
        <p data-testid="recommendations-loading">Scoring candidates…</p>
      )}
      {state.error && (
        <p className="onboarding-error" data-testid="recommendations-error">
          {state.error}
        </p>
      )}
      {!state.loading && !state.error && state.recommendations.length === 0 && (
        <p data-testid="recommendations-empty">
          No properties matched your filters
          {state.candidatesConsidered !== null
            ? ` (${state.candidatesConsidered} considered)`
            : ''}
          . Try broadening your geography or budget.
        </p>
      )}

      <ul className="recommendation-grid" data-testid="recommendation-grid">
        {state.recommendations.map((rec) => (
          <li
            key={rec.property_id}
            className="recommendation-card"
            data-testid={`recommendation-card-${rec.property_id}`}
          >
            <header>
              <strong>{rec.address}</strong>
              <span className="recommendation-score" title="Composite score 0–1">
                {(rec.score * 100).toFixed(0)}
              </span>
            </header>
            <dl>
              <dt>Asking</dt>
              <dd>¥{rec.asking_price.toLocaleString()}</dd>
              {rec.property_type && (
                <>
                  <dt>Type</dt>
                  <dd>{rec.property_type}</dd>
                </>
              )}
              {rec.sqft != null && (
                <>
                  <dt>Area</dt>
                  <dd>{rec.sqft}m²</dd>
                </>
              )}
            </dl>
            <ul className="recommendation-rationale">
              {rec.rationale.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
            <button
              type="button"
              className="onboarding-primary"
              onClick={() => onSelect(rec.property_id)}
              data-testid={`recommendation-select-${rec.property_id}`}
            >
              Simulate with this property
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
