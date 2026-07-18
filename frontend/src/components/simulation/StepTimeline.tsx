import type { ReactNode } from 'react'

export interface TimelineStep {
  type: string
  label: string
  detail?: string | null
  at?: string
}

interface StepTimelineProps {
  steps: TimelineStep[]
  status: 'connecting' | 'streaming' | 'closed' | 'error'
  errorMessage?: string | null
}

const STATUS_LABEL: Record<StepTimelineProps['status'], string> = {
  connecting: '接続中',
  streaming: '進行中',
  closed: '完了',
  error: 'エラー',
}

export default function StepTimeline({
  steps,
  status,
  errorMessage,
}: StepTimelineProps): ReactNode {
  return (
    <div className="step-timeline" data-testid="step-timeline">
      <header className="step-timeline__header">
        <h3>実行ログ</h3>
        <span
          className={`step-timeline__badge step-timeline__badge--${status}`}
          data-testid="step-timeline-status"
        >
          {STATUS_LABEL[status]}
        </span>
      </header>
      {errorMessage && (
        <p className="step-timeline__error" data-testid="step-timeline-error">
          {errorMessage}
        </p>
      )}
      <ol className="step-timeline__list">
        {steps.map((step, i) => (
          <li
            key={`${step.type}-${i}`}
            className="step-timeline__item"
            data-testid={`step-timeline-item-${step.type}`}
          >
            <strong>{step.label}</strong>
            {step.detail && <span className="step-timeline__detail"> — {step.detail}</span>}
            {step.at && (
              <time className="step-timeline__time">
                {new Date(step.at).toLocaleTimeString()}
              </time>
            )}
          </li>
        ))}
        {status === 'streaming' && steps.length === 0 && (
          <li className="step-timeline__empty">最初のイベントを待っています…</li>
        )}
      </ol>
    </div>
  )
}
