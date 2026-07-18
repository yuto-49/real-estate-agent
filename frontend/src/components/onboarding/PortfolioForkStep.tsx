interface PortfolioForkStepProps {
  onAnswer: (hasPortfolio: boolean) => void
}

export default function PortfolioForkStep({ onAnswer }: PortfolioForkStepProps) {
  return (
    <div className="onboarding-fork" data-testid="onboarding-fork">
      <h3>すでに保有ポートフォリオはありますか？</h3>
      <p className="onboarding-subtle">
        現在の運用状況に合わせて、日本の不動産投資向けに初期設定します。
      </p>
      <div className="onboarding-fork__choices">
        <button
          type="button"
          className="onboarding-card"
          onClick={() => onAnswer(true)}
          data-testid="fork-yes"
        >
          <strong>はい、あります</strong>
          <span>CSV または対話入力で保有物件を取り込みます。</span>
        </button>
        <button
          type="button"
          className="onboarding-card"
          onClick={() => onAnswer(false)}
          data-testid="fork-no"
        >
          <strong>まだありません</strong>
          <span>投資方針と予算を入力すると、日本向けの候補物件を提案します。</span>
        </button>
      </div>
    </div>
  )
}
