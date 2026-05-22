import type { ImportMethod } from '../../pages/OnboardingWizard'

interface ImportMethodPickerProps {
  onPick: (method: ImportMethod) => void
}

export default function ImportMethodPicker({ onPick }: ImportMethodPickerProps) {
  return (
    <div className="onboarding-import-picker" data-testid="onboarding-import-picker">
      <h3>How would you like to import your portfolio?</h3>
      <div className="onboarding-import-picker__choices">
        <button
          type="button"
          className="onboarding-card"
          onClick={() => onPick('csv')}
          data-testid="import-csv"
        >
          <strong>Upload a CSV</strong>
          <span>
            Download our template, fill in your holdings, drop it back. Best
            for many properties at once.
          </span>
        </button>
        <button
          type="button"
          className="onboarding-card"
          onClick={() => onPick('chat')}
          data-testid="import-chat"
        >
          <strong>Chat with the assistant</strong>
          <span>
            Describe each property in your own words. We'll extract the
            structured fields and ask you to confirm.
          </span>
        </button>
      </div>
      <p className="onboarding-placeholder">
        Detailed import flow ships in P2 (CSV) and P3 (chat).
      </p>
    </div>
  )
}
