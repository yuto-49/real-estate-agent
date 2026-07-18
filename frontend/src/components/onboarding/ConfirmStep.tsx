import { useState } from 'react'

import type { WizardState } from '../../pages/OnboardingWizard'
import {
  formatBooleanJa,
  formatImportMethodLabel,
  formatJpyCompact,
  formatStrategyLabel,
} from '../../utils/japan'

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
      <h3>試算を開始する準備ができました</h3>
      <dl className="onboarding-summary">
        <dt>既存ポートフォリオ</dt>
        <dd>{state.hasPortfolio === null ? '—' : formatBooleanJa(state.hasPortfolio)}</dd>

        {state.hasPortfolio && (
          <>
            <dt>取り込み方法</dt>
            <dd>{formatImportMethodLabel(state.importMethod)}</dd>
            {state.importedPortfolioId && (
              <>
                <dt>ポートフォリオ</dt>
                <dd>
                  <code>{state.importedPortfolioId.slice(0, 8)}…</code>
                </dd>
              </>
            )}
            {state.importSummary && (
              <>
                <dt>反映件数</dt>
                <dd>
                  新規 {state.importSummary.inserted} 件 ・ 更新 {state.importSummary.updated} 件
                </dd>
              </>
            )}
          </>
        )}

        {state.hasPortfolio === false && (
          <>
            <dt>投資方針</dt>
            <dd>{formatStrategyLabel(state.profile.strategy)}</dd>
            <dt>予算</dt>
            <dd>
              {formatJpyCompact(state.profile.budget)}
            </dd>
            <dt>選択物件</dt>
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
            {launching ? '開始中…' : 'シミュレーション開始'}
          </button>
        )}
        <button
          type="button"
          className="onboarding-secondary"
          onClick={onSkipToPortfolio}
          data-testid="confirm-skip"
        >
          {canSimulate ? '今回はスキップしてポートフォリオへ' : 'ポートフォリオへ移動'}
        </button>
      </div>
    </div>
  )
}
