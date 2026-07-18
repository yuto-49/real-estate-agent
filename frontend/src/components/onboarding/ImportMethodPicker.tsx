import type { ImportMethod } from '../../pages/OnboardingWizard'

interface ImportMethodPickerProps {
  onPick: (method: ImportMethod) => void
}

export default function ImportMethodPicker({ onPick }: ImportMethodPickerProps) {
  return (
    <div className="onboarding-import-picker" data-testid="onboarding-import-picker">
      <h3>既存ポートフォリオの取り込み方法を選んでください</h3>
      <div className="onboarding-import-picker__choices">
        <button
          type="button"
          className="onboarding-card"
          onClick={() => onPick('csv')}
          data-testid="import-csv"
        >
          <strong>CSV をアップロード</strong>
          <span>
            テンプレートを使って保有物件をまとめて登録できます。
            複数物件を一度に取り込みたい場合に向いています。
          </span>
        </button>
        <button
          type="button"
          className="onboarding-card"
          onClick={() => onPick('chat')}
          data-testid="import-chat"
        >
          <strong>対話で入力</strong>
          <span>
            物件概要を文章で入力すると、所在地や賃料などを自動整理して
            確認画面に反映します。
          </span>
        </button>
      </div>
      <p className="onboarding-placeholder">
        日本の収益不動産ポートフォリオをそのまま整理できるように設計しています。
      </p>
    </div>
  )
}
