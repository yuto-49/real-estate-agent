interface PortfolioForkStepProps {
  onAnswer: (hasPortfolio: boolean) => void
}

export default function PortfolioForkStep({ onAnswer }: PortfolioForkStepProps) {
  return (
    <div className="onboarding-fork" data-testid="onboarding-fork">
      <h3>Do you have an existing portfolio?</h3>
      <p className="onboarding-subtle">
        Tell us where you are today so we can tailor the simulation.
      </p>
      <div className="onboarding-fork__choices">
        <button
          type="button"
          className="onboarding-card"
          onClick={() => onAnswer(true)}
          data-testid="fork-yes"
        >
          <strong>Yes, I have one</strong>
          <span>Import via CSV or chat with the assistant.</span>
        </button>
        <button
          type="button"
          className="onboarding-card"
          onClick={() => onAnswer(false)}
          data-testid="fork-no"
        >
          <strong>Not yet</strong>
          <span>Tell us your strategy and budget — we'll suggest properties.</span>
        </button>
      </div>
    </div>
  )
}
