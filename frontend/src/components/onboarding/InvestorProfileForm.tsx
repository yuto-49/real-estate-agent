import type { ChangeEvent, FormEvent } from 'react'

import type { InvestorProfileDraft, StrategyKind } from '../../pages/OnboardingWizard'

interface InvestorProfileFormProps {
  value: InvestorProfileDraft
  onChange: (patch: Partial<InvestorProfileDraft>) => void
  onSubmit: () => void
}

const STRATEGY_OPTIONS: { value: StrategyKind; label: string }[] = [
  { value: 'buy_and_hold', label: 'Buy and hold' },
  { value: 'flip', label: 'Flip' },
  { value: 'lease', label: 'Lease' },
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
    Boolean(p.geography.city) ||
    Boolean(p.geography.state)
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

  const handleGeoChange = (key: 'zip' | 'city' | 'state') =>
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
      <h3>Tell us about your investing goals</h3>

      <label className="onboarding-field">
        <span>Investment budget (JPY)</span>
        <input
          type="number"
          min="0"
          step="1000"
          value={value.budget ?? ''}
          onChange={(e) => onChange({ budget: parseNumeric(e.target.value) })}
          data-testid="profile-budget"
          required
        />
      </label>

      <fieldset className="onboarding-field onboarding-field--radio">
        <legend>Strategy</legend>
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
          <span>Target cap rate (%)</span>
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
          <span>Target CoC (%)</span>
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
        <legend>Geography (at least one required)</legend>
        <input
          type="text"
          placeholder="ZIP"
          value={value.geography.zip ?? ''}
          onChange={handleGeoChange('zip')}
          data-testid="profile-zip"
        />
        <input
          type="text"
          placeholder="City"
          value={value.geography.city ?? ''}
          onChange={handleGeoChange('city')}
          data-testid="profile-city"
        />
        <input
          type="text"
          placeholder="State"
          value={value.geography.state ?? ''}
          onChange={handleGeoChange('state')}
          data-testid="profile-state"
        />
      </fieldset>

      <button
        type="submit"
        className="onboarding-primary"
        disabled={!isComplete(value)}
        data-testid="profile-submit"
      >
        See recommendations
      </button>
    </form>
  )
}
