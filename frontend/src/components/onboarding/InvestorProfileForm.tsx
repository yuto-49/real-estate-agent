import type { ChangeEvent, FormEvent } from 'react'

import type { InvestorProfileDraft, StrategyKind } from '../../pages/OnboardingWizard'
import { PREFECTURES, formatStrategyLabel } from '../../utils/japan'

interface InvestorProfileFormProps {
  value: InvestorProfileDraft
  onChange: (patch: Partial<InvestorProfileDraft>) => void
  onSubmit: () => void
}

const STRATEGY_OPTIONS: { value: StrategyKind; label: string }[] = [
  { value: 'buy_and_hold', label: formatStrategyLabel('buy_and_hold') },
  { value: 'flip', label: formatStrategyLabel('flip') },
  { value: 'lease', label: formatStrategyLabel('lease') },
]

function parseNumeric(raw: string): number | null {
  if (raw.trim() === '') return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

function isComplete(p: InvestorProfileDraft): boolean {
  if (p.budget === null || p.budget <= 0) return false
  if (p.strategy === null) return false
  if (p.target_cap_rate === null) return false
  if (p.target_coc === null) return false
  const hasGeo =
    Boolean(p.geography.zip) ||
    Boolean(p.geography.prefecture) ||
    Boolean(p.geography.municipality) ||
    Boolean(p.geography.neighborhood)
  return hasGeo
}

export default function InvestorProfileForm({
  value,
  onChange,
  onSubmit,
}: InvestorProfileFormProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (isComplete(value)) onSubmit()
  }

  const handleGeoChange = (
    key: 'zip' | 'prefecture' | 'municipality' | 'ward' | 'neighborhood' | 'station',
  ) =>
    (event: ChangeEvent<HTMLInputElement>) => {
      onChange({
        geography: { ...value.geography, [key]: event.target.value || undefined },
      })
    }

  return (
    <form
      className="onboarding-profile"
      onSubmit={handleSubmit}
      data-testid="onboarding-profile"
    >
      <h3>日本での投資条件を設定してください</h3>

      <label className="onboarding-field">
        <span>投資予算（円）</span>
        <input
          type="number"
          min="0"
          step="10000"
          value={value.budget ?? ''}
          onChange={(e) => onChange({ budget: parseNumeric(e.target.value) })}
          data-testid="profile-budget"
          required
        />
      </label>

      <fieldset className="onboarding-field onboarding-field--radio">
        <legend>投資方針</legend>
        {STRATEGY_OPTIONS.map((opt) => (
          <label key={opt.value}>
            <input
              type="radio"
              name="strategy"
              value={opt.value}
              checked={value.strategy === opt.value}
              onChange={() => onChange({ strategy: opt.value })}
              data-testid={`profile-strategy-${opt.value}`}
            />
            {opt.label}
          </label>
        ))}
      </fieldset>

      <div className="onboarding-field-row">
        <label className="onboarding-field">
          <span>目標表面利回り（%）</span>
          <input
            type="number"
            min="0"
            step="0.1"
            value={value.target_cap_rate ?? ''}
            onChange={(e) =>
              onChange({ target_cap_rate: parseNumeric(e.target.value) })
            }
            data-testid="profile-cap-rate"
            required
          />
        </label>
        <label className="onboarding-field">
          <span>目標自己資金利回り（%）</span>
          <input
            type="number"
            min="0"
            step="0.1"
            value={value.target_coc ?? ''}
            onChange={(e) =>
              onChange({ target_coc: parseNumeric(e.target.value) })
            }
            data-testid="profile-coc"
            required
          />
        </label>
      </div>

      <fieldset className="onboarding-field onboarding-field--row">
        <legend>希望エリア（いずれか必須）</legend>
        <input
          type="text"
          placeholder="郵便番号"
          value={value.geography.zip ?? ''}
          onChange={handleGeoChange('zip')}
          data-testid="profile-zip"
        />
        <select
          value={value.geography.prefecture ?? ''}
          onChange={(e) =>
            onChange({
              geography: { ...value.geography, prefecture: e.target.value || undefined },
            })
          }
          data-testid="profile-prefecture"
        >
          <option value="">都道府県を選択</option>
          {PREFECTURES.map((prefecture) => (
            <option key={prefecture} value={prefecture}>
              {prefecture}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="市区町村"
          value={value.geography.municipality ?? ''}
          onChange={handleGeoChange('municipality')}
          data-testid="profile-municipality"
        />
        <input
          type="text"
          placeholder="町名・丁目"
          value={value.geography.neighborhood ?? ''}
          onChange={handleGeoChange('neighborhood')}
          data-testid="profile-neighborhood"
        />
      </fieldset>
      <div className="onboarding-field-row">
        <label className="onboarding-field">
          <span>最寄り駅（任意）</span>
          <input
            type="text"
            placeholder="例: 新宿"
            value={value.geography.station ?? ''}
            onChange={handleGeoChange('station')}
            data-testid="profile-station"
          />
        </label>
        <label className="onboarding-field">
          <span>行政区（任意）</span>
          <input
            type="text"
            placeholder="例: 港区"
            value={value.geography.ward ?? ''}
            onChange={handleGeoChange('ward')}
            data-testid="profile-ward"
          />
        </label>
      </div>

      <button
        type="submit"
        className="onboarding-primary"
        disabled={!isComplete(value)}
        data-testid="profile-submit"
      >
        候補物件を見る
      </button>
    </form>
  )
}
