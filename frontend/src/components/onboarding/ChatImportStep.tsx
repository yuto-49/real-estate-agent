import { useState, type FormEvent } from 'react'

import { useAuth } from '../../hooks/useAuth'
import { api } from '../../utils/api'
import type { PortfolioHoldingCreate } from '../../utils/types'

interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

interface ChatImportStepProps {
  onImported: (portfolioId: string, summary: { inserted: number; updated: number }) => void
}

/**
 * Conversational portfolio import. The user describes their holdings in free
 * text; the backend invokes Claude with a structured `record_portfolio_holdings`
 * tool. The extracted rows accumulate in an editable preview table and are
 * only committed once the user clicks "Confirm".
 */
export default function ChatImportStep({ onImported }: ChatImportStepProps) {
  const { user } = useAuth()
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const [holdings, setHoldings] = useState<PortfolioHoldingCreate[]>([])
  const [error, setError] = useState<string | null>(null)
  const [committing, setCommitting] = useState(false)

  const send = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const text = input.trim()
    if (!text || pending) return

    const nextTurns: ChatTurn[] = [...turns, { role: 'user', content: text }]
    setTurns(nextTurns)
    setInput('')
    setPending(true)
    setError(null)

    try {
      const result = await api.portfolio.chatExtract({ messages: nextTurns })
      if (result.narration) {
        setTurns([...nextTurns, { role: 'assistant', content: result.narration }])
      }
      if (result.holdings.length > 0) {
        // Dedupe by lowercased address — later turns override earlier ones.
        const merged = new Map<string, PortfolioHoldingCreate>()
        for (const h of [...holdings, ...result.holdings]) {
          merged.set(h.address.trim().toLowerCase(), h)
        }
        setHoldings(Array.from(merged.values()))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Extraction failed')
    } finally {
      setPending(false)
    }
  }

  const updateHolding = (
    index: number,
    patch: Partial<PortfolioHoldingCreate>,
  ) => {
    setHoldings((prev) =>
      prev.map((h, i) => (i === index ? { ...h, ...patch } : h)),
    )
  }

  const removeHolding = (index: number) => {
    setHoldings((prev) => prev.filter((_, i) => i !== index))
  }

  const commit = async () => {
    setError(null)
    if (!user?.id) {
      setError('You must be signed in to import a portfolio.')
      return
    }
    if (holdings.length === 0) return

    setCommitting(true)
    try {
      const result = await api.portfolio.chatConfirm({
        user_id: user.id,
        user_email: user.email,
        holdings,
      })
      onImported(result.portfolio_id, {
        inserted: result.inserted_count,
        updated: result.updated_count,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Commit failed')
    } finally {
      setCommitting(false)
    }
  }

  return (
    <div className="onboarding-chat-step" data-testid="onboarding-chat-step">
      <h3>Tell us about your holdings</h3>
      <p className="onboarding-subtle">
        Describe each property in your own words — address, value, rent,
        loan. The assistant will fill in a table you can edit before saving.
      </p>

      <ul className="chat-transcript" data-testid="chat-transcript">
        {turns.map((turn, i) => (
          <li key={i} className={`chat-turn chat-turn--${turn.role}`}>
            <strong>{turn.role === 'user' ? 'You' : 'Assistant'}:</strong>{' '}
            {turn.content}
          </li>
        ))}
      </ul>

      <form onSubmit={send} className="chat-input-row">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. I own 123 Main St 60601, worth ~$420k, $2,400/mo rent"
          disabled={pending}
          data-testid="chat-input"
        />
        <button type="submit" disabled={pending || !input.trim()} data-testid="chat-send">
          {pending ? 'Thinking…' : 'Send'}
        </button>
      </form>

      {holdings.length > 0 && (
        <div className="chat-confirm" data-testid="chat-confirm-preview">
          <h4>Review extracted holdings ({holdings.length})</h4>
          <table className="csv-import-table">
            <thead>
              <tr>
                <th>Address</th>
                <th>Zip</th>
                <th>Asset class</th>
                <th>Monthly rent</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {holdings.map((h, i) => (
                <tr key={`${h.address}-${i}`}>
                  <td>
                    <input
                      value={h.address}
                      onChange={(e) =>
                        updateHolding(i, { address: e.target.value })
                      }
                    />
                  </td>
                  <td>
                    <input
                      value={h.zip_code ?? ''}
                      onChange={(e) =>
                        updateHolding(i, { zip_code: e.target.value || null })
                      }
                    />
                  </td>
                  <td>
                    <input
                      value={h.asset_class ?? 'sfr'}
                      onChange={(e) =>
                        updateHolding(i, { asset_class: e.target.value })
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      value={h.financials?.monthly_rent ?? ''}
                      onChange={(e) =>
                        updateHolding(i, {
                          financials: {
                            ...(h.financials ?? {}),
                            monthly_rent:
                              e.target.value === '' ? null : Number(e.target.value),
                          },
                        })
                      }
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      onClick={() => removeHolding(i)}
                      data-testid={`chat-remove-${i}`}
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            type="button"
            onClick={() => void commit()}
            disabled={committing}
            className="onboarding-primary"
            data-testid="chat-commit"
          >
            {committing ? 'Saving…' : `Confirm ${holdings.length} holding(s)`}
          </button>
        </div>
      )}

      {error && (
        <p className="onboarding-error" data-testid="chat-import-error">
          {error}
        </p>
      )}
    </div>
  )
}
