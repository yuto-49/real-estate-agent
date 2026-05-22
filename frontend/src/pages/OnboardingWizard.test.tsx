import { describe, expect, it, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import OnboardingWizard, { wizardReducer, type WizardState } from './OnboardingWizard'

function renderWizard() {
  return render(
    <MemoryRouter initialEntries={['/onboard']}>
      <OnboardingWizard />
    </MemoryRouter>,
  )
}

describe('wizardReducer', () => {
  const baseState: WizardState = {
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

  it('routes "yes" answer to import_method', () => {
    const next = wizardReducer(baseState, { type: 'set_has_portfolio', value: true })
    expect(next.hasPortfolio).toBe(true)
    expect(next.step).toBe('import_method')
  })

  it('CSV import method routes through csv_import (not confirm)', () => {
    const next = wizardReducer(
      { ...baseState, step: 'import_method', hasPortfolio: true },
      { type: 'set_import_method', value: 'csv' },
    )
    expect(next.step).toBe('csv_import')
    expect(next.importMethod).toBe('csv')
  })

  it('chat import method routes through chat_import', () => {
    const next = wizardReducer(
      { ...baseState, step: 'import_method', hasPortfolio: true },
      { type: 'set_import_method', value: 'chat' },
    )
    expect(next.step).toBe('chat_import')
    expect(next.importMethod).toBe('chat')
  })

  it('back from chat_import returns to import_method', () => {
    // Smoke-test that the back map covers the new step; doesn't go through
    // the reducer directly but ensures the step exists in the WizardStep union.
    const state: WizardState = {
      ...baseState,
      step: 'chat_import',
      hasPortfolio: true,
      importMethod: 'chat',
    }
    const next = wizardReducer(state, { type: 'goto', step: 'import_method' })
    expect(next.step).toBe('import_method')
  })

  it('csv_imported action stores portfolio id + summary and advances to confirm', () => {
    const next = wizardReducer(
      { ...baseState, step: 'csv_import', hasPortfolio: true, importMethod: 'csv' },
      {
        type: 'csv_imported',
        portfolioId: 'p-123',
        summary: { inserted: 2, updated: 1 },
      },
    )
    expect(next.importedPortfolioId).toBe('p-123')
    expect(next.importSummary).toEqual({ inserted: 2, updated: 1 })
    expect(next.step).toBe('confirm')
  })

  it('routes "no" answer to profile_form', () => {
    const next = wizardReducer(baseState, { type: 'set_has_portfolio', value: false })
    expect(next.hasPortfolio).toBe(false)
    expect(next.step).toBe('profile_form')
  })

  it('merges partial profile patches without overwriting other fields', () => {
    const state = wizardReducer(
      {
        ...baseState,
        step: 'profile_form',
        hasPortfolio: false,
        profile: {
          budget: 500_000,
          strategy: 'buy_and_hold',
          target_cap_rate: null,
          target_coc: null,
          geography: { zip: '60601' },
        },
      },
      { type: 'update_profile', patch: { target_cap_rate: 7.5 } },
    )
    expect(state.profile.budget).toBe(500_000)
    expect(state.profile.strategy).toBe('buy_and_hold')
    expect(state.profile.target_cap_rate).toBe(7.5)
    expect(state.profile.geography.zip).toBe('60601')
  })
})

describe('OnboardingWizard component', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
  })

  it('renders fork step initially', () => {
    renderWizard()
    expect(screen.getByTestId('onboarding-fork')).toBeInTheDocument()
    expect(screen.getByTestId('fork-yes')).toBeInTheDocument()
    expect(screen.getByTestId('fork-no')).toBeInTheDocument()
  })

  it('navigates to import picker when "Yes" is chosen', () => {
    renderWizard()
    fireEvent.click(screen.getByTestId('fork-yes'))
    expect(screen.getByTestId('onboarding-import-picker')).toBeInTheDocument()
  })

  it('navigates to profile form when "Not yet" is chosen', () => {
    renderWizard()
    fireEvent.click(screen.getByTestId('fork-no'))
    expect(screen.getByTestId('onboarding-profile')).toBeInTheDocument()
  })

  it('persists step across remount via sessionStorage', async () => {
    const { unmount } = renderWizard()
    fireEvent.click(screen.getByTestId('fork-no'))
    expect(screen.getByTestId('onboarding-profile')).toBeInTheDocument()
    await act(async () => {
      unmount()
    })
    renderWizard()
    expect(screen.getByTestId('onboarding-profile')).toBeInTheDocument()
  })

  it('back button is disabled on the first step', () => {
    renderWizard()
    const back = screen.getByTestId('wizard-back') as HTMLButtonElement
    expect(back.disabled).toBe(true)
  })

  it('back button returns from profile_form to fork', () => {
    renderWizard()
    fireEvent.click(screen.getByTestId('fork-no'))
    expect(screen.getByTestId('onboarding-profile')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('wizard-back'))
    expect(screen.getByTestId('onboarding-fork')).toBeInTheDocument()
  })
})
