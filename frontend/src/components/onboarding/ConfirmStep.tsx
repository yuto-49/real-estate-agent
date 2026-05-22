import { useState } from 'react'

import type { WizardState } from '../../pages/OnboardingWizard'

interface ConfirmStepProps {
  state: WizardState
  onLaunchSimulation: () => Promise<void> | void
  onSkipToPortfolio: () => void
}

export default function ConfirmStep({
  state,
  onLaunchSimulation,
  onSkipToPortfolio,
}: ConfirmStepProps) {
  const [launching, setLaunching] = useState(false)
  const canSimulate = Boolean(state.importedPortfolioId)
  const handleLaunch = async () => {
    setLaunching(true)
    try {
      await onLaunchSimulation()
    } finally {
      setLaunching(false)
    }
  }
  return (
    <div className="onboarding-confirm" data-testid="onboarding-confirm">
      <h3>Ready to launch</h3>
      <dl className="onboarding-summary">
        <dt>Has portfolio</dt>
        <dd>{state.hasPortfolio === null ? '—' : state.hasPortfolio ? 'Yes' : 'No'}</dd>

        {state.hasPortfolio && (
          <>
            <dt>Import method</dt>
            <dd>{state.importMethod ?? '—'}</dd>
            {state.importedPortfolioId && (
              <>
                <dt>Portfolio</dt>
                <dd>
                  <code>{state.importedPortfolioId.slice(0, 8)}…</code>
                </dd>
              </>
            )}
            {state.importSummary && (
              <>
                <dt>Imported</dt>
                <dd>
                  {state.importSummary.inserted} new ·{' '}
                  {state.importSummary.updated} updated
                </dd>
              </>
            )}
          </>
        )}

        {state.hasPortfolio === false && (
          <>
            <dt>Strategy</dt>
            <dd>{state.profile.strategy ?? '—'}</dd>
            <dt>Budget</dt>
            <dd>
              {state.profile.budget !== null
                ? `$${state.profile.budget.toLocaleString()}`
                : '—'}
            </dd>
            <dt>Selected property</dt>
            <dd>{state.selectedPropertyId ?? '—'}</dd>
          </>
        )}
      </dl>
      <div className="onboarding-confirm__actions">
        {canSimulate && (
          <button
            type="button"
            className="onboarding-primary"
            onClick={() => void handleLaunch()}
            disabled={launching}
            data-testid="confirm-launch-simulation"
          >
            {launching ? 'Launching…' : 'Run simulation'}
          </button>
        )}
        <button
          type="button"
          className="onboarding-secondary"
          onClick={onSkipToPortfolio}
          data-testid="confirm-skip"
        >
          {canSimulate ? 'Skip for now — go to portfolio' : 'Go to portfolio'}
        </button>
      </div>
    </div>
  )
}
