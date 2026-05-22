import { useEffect, useReducer, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../hooks/useAuth'
import { api } from '../utils/api'

import ChatImportStep from '../components/onboarding/ChatImportStep'
import ConfirmStep from '../components/onboarding/ConfirmStep'
import CsvImportStep from '../components/onboarding/CsvImportStep'
import ImportMethodPicker from '../components/onboarding/ImportMethodPicker'
import InvestorProfileForm from '../components/onboarding/InvestorProfileForm'
import PortfolioForkStep from '../components/onboarding/PortfolioForkStep'
import RecommendationList from '../components/onboarding/RecommendationList'

export type WizardStep =
  | 'fork'
  | 'import_method'
  | 'csv_import'
  | 'chat_import'
  | 'profile_form'
  | 'recommendations'
  | 'confirm'

export type ImportMethod = 'csv' | 'chat'
export type StrategyKind = 'buy_and_hold' | 'flip' | 'lease'

export interface InvestorProfileDraft {
  budget: number | null
  strategy: StrategyKind | null
  target_cap_rate: number | null
  target_coc: number | null
  geography: {
    zip?: string
    city?: string
    state?: string
  }
}

export interface WizardState {
  step: WizardStep
  hasPortfolio: boolean | null
  importMethod: ImportMethod | null
  profile: InvestorProfileDraft
  selectedPropertyId: string | null
  importedPortfolioId: string | null
  importSummary: { inserted: number; updated: number } | null
}

type WizardAction =
  | { type: 'set_has_portfolio'; value: boolean }
  | { type: 'set_import_method'; value: ImportMethod }
  | { type: 'csv_imported'; portfolioId: string; summary: { inserted: number; updated: number } }
  | { type: 'update_profile'; patch: Partial<InvestorProfileDraft> }
  | { type: 'select_property'; propertyId: string }
  | { type: 'goto'; step: WizardStep }
  | { type: 'reset' }

const STORAGE_KEY = 'onboardingWizard:v1'

const initialState: WizardState = {
  step: 'fork',
  hasPortfolio: null,
  importMethod: null,
  profile: {
    budget: null,
    strategy: null,
    target_cap_rate: null,
    target_coc: null,
    geography: {},
  },
  selectedPropertyId: null,
  importedPortfolioId: null,
  importSummary: null,
}

function loadPersistedState(): WizardState {
  if (typeof window === 'undefined') return initialState
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return initialState
    const parsed = JSON.parse(raw) as Partial<WizardState>
    return { ...initialState, ...parsed }
  } catch {
    return initialState
  }
}

function persistState(state: WizardState): void {
  if (typeof window === 'undefined') return
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // ignore quota / disabled-storage errors
  }
}

export function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'set_has_portfolio':
      return {
        ...state,
        hasPortfolio: action.value,
        step: action.value ? 'import_method' : 'profile_form',
      }
    case 'set_import_method':
      return {
        ...state,
        importMethod: action.value,
        step: action.value === 'csv' ? 'csv_import' : 'chat_import',
      }
    case 'csv_imported':
      return {
        ...state,
        importedPortfolioId: action.portfolioId,
        importSummary: action.summary,
        step: 'confirm',
      }
    case 'update_profile':
      return {
        ...state,
        profile: { ...state.profile, ...action.patch },
      }
    case 'select_property':
      return {
        ...state,
        selectedPropertyId: action.propertyId,
        step: 'confirm',
      }
    case 'goto':
      return { ...state, step: action.step }
    case 'reset':
      return initialState
    default:
      return state
  }
}

interface WizardChromeProps {
  step: WizardStep
  onBack: () => void
  canGoBack: boolean
  children: ReactNode
}

function WizardChrome({ step, onBack, canGoBack, children }: WizardChromeProps) {
  const labels: Record<WizardStep, string> = {
    fork: 'Portfolio',
    import_method: 'Import',
    csv_import: 'CSV',
    chat_import: 'Chat',
    profile_form: 'Profile',
    recommendations: 'Recommendations',
    confirm: 'Confirm',
  }
  const order: WizardStep[] = [
    'fork',
    'import_method',
    'csv_import',
    'chat_import',
    'profile_form',
    'recommendations',
    'confirm',
  ]
  const currentIdx = order.indexOf(step)

  return (
    <div className="onboarding-wizard" data-testid="onboarding-wizard">
      <header className="onboarding-wizard__header">
        <h2>Get started</h2>
        <ol className="onboarding-wizard__progress" aria-label="Progress">
          {order.map((s, i) => (
            <li
              key={s}
              className={i === currentIdx ? 'is-current' : i < currentIdx ? 'is-done' : ''}
              data-testid={`wizard-step-pill-${s}`}
            >
              {labels[s]}
            </li>
          ))}
        </ol>
      </header>
      <section className="onboarding-wizard__body">{children}</section>
      <footer className="onboarding-wizard__footer">
        <button
          type="button"
          onClick={onBack}
          disabled={!canGoBack}
          data-testid="wizard-back"
        >
          Back
        </button>
      </footer>
    </div>
  )
}

export default function OnboardingWizard() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [state, dispatch] = useReducer(wizardReducer, undefined, loadPersistedState)
  const [profileError, setProfileError] = useState<string | null>(null)

  useEffect(() => {
    persistState(state)
  }, [state])

  const submitProfile = async () => {
    setProfileError(null)
    if (!user?.id) {
      setProfileError('You must be signed in to save your profile.')
      return
    }
    try {
      await api.investorProfile.upsert({
        user_id: user.id,
        user_email: user.email,
        budget: state.profile.budget,
        strategy: state.profile.strategy,
        target_cap_rate: state.profile.target_cap_rate,
        target_coc: state.profile.target_coc,
        geography: state.profile.geography,
      })
      dispatch({ type: 'goto', step: 'recommendations' })
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : 'Failed to save profile.')
    }
  }

  const canGoBack = state.step !== 'fork'
  const onBack = () => {
    const backMap: Partial<Record<WizardStep, WizardStep>> = {
      import_method: 'fork',
      csv_import: 'import_method',
      chat_import: 'import_method',
      profile_form: 'fork',
      recommendations: 'profile_form',
      confirm: state.hasPortfolio
        ? state.importMethod === 'csv'
          ? 'csv_import'
          : state.importMethod === 'chat'
            ? 'chat_import'
            : 'import_method'
        : 'recommendations',
    }
    const target = backMap[state.step]
    if (target) dispatch({ type: 'goto', step: target })
  }

  const renderStep = (): ReactNode => {
    switch (state.step) {
      case 'fork':
        return (
          <PortfolioForkStep
            onAnswer={(v) => dispatch({ type: 'set_has_portfolio', value: v })}
          />
        )
      case 'import_method':
        return (
          <ImportMethodPicker
            onPick={(method) => dispatch({ type: 'set_import_method', value: method })}
          />
        )
      case 'csv_import':
        return (
          <CsvImportStep
            onImported={(portfolioId, summary) =>
              dispatch({ type: 'csv_imported', portfolioId, summary })
            }
          />
        )
      case 'chat_import':
        return (
          <ChatImportStep
            onImported={(portfolioId, summary) =>
              dispatch({ type: 'csv_imported', portfolioId, summary })
            }
          />
        )
      case 'profile_form':
        return (
          <>
            <InvestorProfileForm
              value={state.profile}
              onChange={(patch) => dispatch({ type: 'update_profile', patch })}
              onSubmit={() => void submitProfile()}
            />
            {profileError && (
              <p className="onboarding-error" data-testid="profile-form-error">
                {profileError}
              </p>
            )}
          </>
        )
      case 'recommendations':
        return (
          <>
            {profileError && (
              <p className="onboarding-error" data-testid="recommendation-error">
                {profileError}
              </p>
            )}
            <RecommendationList
              profile={state.profile}
              onSelect={async (propertyId) => {
              setProfileError(null)
              if (!user?.id) {
                setProfileError('You must be signed in to select a property.')
                return
              }
              try {
                const portfolio = await api.portfolio.fromProperty({
                  user_id: user.id,
                  user_email: user.email,
                  property_id: propertyId,
                  portfolio_name: 'Recommended Property',
                  investment_strategy: 'buy_hold',
                })
                dispatch({ type: 'select_property', propertyId })
                dispatch({
                  type: 'csv_imported',
                  portfolioId: portfolio.id,
                  summary: { inserted: 1, updated: 0 },
                })
              } catch (err) {
                setProfileError(
                  err instanceof Error
                    ? err.message
                    : 'Could not stage the selected property.',
                )
              }
            }}
            />
          </>
        )
      case 'confirm':
        return (
          <ConfirmStep
            state={state}
            onLaunchSimulation={async () => {
              const portfolioId = state.importedPortfolioId
              if (!portfolioId) {
                navigate('/portfolio')
                return
              }
              try {
                const launch = await api.strategy.run({
                  portfolio_id: portfolioId,
                  text: state.profile.strategy
                    ? `Strategy: ${state.profile.strategy}. Target cap rate ${state.profile.target_cap_rate ?? 'unset'}%.`
                    : 'Default strategy run.',
                })
                dispatch({ type: 'reset' })
                navigate(`/simulate/${launch.run_id}`)
              } catch (err) {
                setProfileError(
                  err instanceof Error ? err.message : 'Could not launch simulation.',
                )
              }
            }}
            onSkipToPortfolio={() => {
              dispatch({ type: 'reset' })
              navigate('/portfolio')
            }}
          />
        )
      default:
        return null
    }
  }

  return (
    <WizardChrome step={state.step} onBack={onBack} canGoBack={canGoBack}>
      {renderStep()}
    </WizardChrome>
  )
}
