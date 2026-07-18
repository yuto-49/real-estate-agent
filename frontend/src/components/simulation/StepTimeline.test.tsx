import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import StepTimeline, { type TimelineStep } from './StepTimeline'

function step(over: Partial<TimelineStep> = {}): TimelineStep {
  return {
    type: 'step.analysis_built',
    label: 'Analysis built',
    detail: '1 holding',
    at: '2026-05-18T05:10:00Z',
    ...over,
  }
}

describe('StepTimeline', () => {
  it('renders status pill', () => {
    render(<StepTimeline steps={[]} status="connecting" />)
    expect(screen.getByTestId('step-timeline-status')).toHaveTextContent('接続中')
  })

  it('renders each step with label + detail', () => {
    render(
      <StepTimeline
        steps={[step({ type: 'run.started', label: 'Run started', detail: 'Portfolio p1' })]}
        status="streaming"
      />,
    )
    expect(screen.getByTestId('step-timeline-item-run.started')).toBeInTheDocument()
    expect(screen.getByText('Run started')).toBeInTheDocument()
    expect(screen.getByText(/Portfolio p1/)).toBeInTheDocument()
  })

  it('shows empty state while streaming with no events yet', () => {
    render(<StepTimeline steps={[]} status="streaming" />)
    expect(screen.getByText(/最初のイベントを待っています/)).toBeInTheDocument()
  })

  it('renders error message when status=error', () => {
    render(
      <StepTimeline steps={[]} status="error" errorMessage="WebSocket failed" />,
    )
    expect(screen.getByTestId('step-timeline-error').textContent).toBe('WebSocket failed')
  })

  it('preserves event order', () => {
    const steps: TimelineStep[] = [
      step({ type: 'run.started', label: 'Run started' }),
      step({ type: 'step.analysis_built', label: 'Analysis built' }),
      step({ type: 'step.simulation_projected', label: 'Simulation projected' }),
      step({ type: 'run.completed', label: 'Run completed' }),
    ]
    render(<StepTimeline steps={steps} status="closed" />)
    const items = screen.getAllByRole('listitem')
    expect(items.map((el: HTMLElement) => el.textContent)).toEqual(
      expect.arrayContaining([
        expect.stringContaining('Run started'),
        expect.stringContaining('Analysis built'),
        expect.stringContaining('Simulation projected'),
        expect.stringContaining('Run completed'),
      ]),
    )
  })
})
