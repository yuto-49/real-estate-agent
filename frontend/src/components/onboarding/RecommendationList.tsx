import { useEffect, useState } from 'react'

import { useAuth } from '../../hooks/useAuth'
import { api } from '../../utils/api'
import type {
  InvestorProfileDraft,
} from '../../pages/OnboardingWizard'
import {
  formatJpyCompact,
  formatPropertyTypeLabel,
  formatStrategyLabel,
} from '../../utils/japan'
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
        error: '候補物件を表示するにはログインが必要です。',
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
            err instanceof Error ? err.message : '候補物件を取得できませんでした。',
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
      <h3>おすすめ物件</h3>
      <p className="onboarding-subtle">
        予算 {formatJpyCompact(profile.budget)} ・ 方針 {formatStrategyLabel(profile.strategy)} ・
        目標表面利回り {profile.target_cap_rate ?? '—'}%
      </p>

      {state.loading && (
        <p data-testid="recommendations-loading">候補物件を評価中…</p>
      )}
      {state.error && (
        <p className="onboarding-error" data-testid="recommendations-error">
          {state.error}
        </p>
      )}
      {!state.loading && !state.error && state.recommendations.length === 0 && (
        <p data-testid="recommendations-empty">
          条件に合う物件が見つかりませんでした
          {state.candidatesConsidered !== null
            ? `（候補 ${state.candidatesConsidered} 件を確認）`
            : ''}
          。希望エリアや予算条件を広げて再度お試しください。
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
              <span className="recommendation-score" title="総合スコア">
                {(rec.score * 100).toFixed(0)}
              </span>
            </header>
            <dl>
              <dt>販売価格</dt>
              <dd>{formatJpyCompact(rec.asking_price)}</dd>
              {rec.property_type && (
                <>
                  <dt>物件種別</dt>
                  <dd>{formatPropertyTypeLabel(rec.property_type)}</dd>
                </>
              )}
              {rec.bedrooms !== null && rec.bedrooms !== undefined && (
                <>
                  <dt>部屋数 / 水回り</dt>
                  <dd>
                    {rec.bedrooms} / {rec.bathrooms ?? '—'}
                  </dd>
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
              この物件で試算する
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
