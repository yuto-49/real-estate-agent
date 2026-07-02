import type { InvestorPortfolio, UserProfile } from '../../utils/types'

interface InvestContextBarProps {
  users: UserProfile[]
  selectedUserId: string
  onUserChange: (userId: string) => void
  portfolios: InvestorPortfolio[]
  selectedPortfolioId: string
  onPortfolioChange: (portfolioId: string) => void
  newPortfolioName: string
  onNewPortfolioNameChange: (name: string) => void
  onCreatePortfolio: () => void
}

export default function InvestContextBar({
  users,
  selectedUserId,
  onUserChange,
  portfolios,
  selectedPortfolioId,
  onPortfolioChange,
  newPortfolioName,
  onNewPortfolioNameChange,
  onCreatePortfolio,
}: InvestContextBarProps) {
  return (
    <div className="invest-context-bar" data-testid="invest-context-bar">
      <label>
        Investor
        <select
          value={selectedUserId}
          onChange={(e) => onUserChange(e.target.value)}
          data-testid="invest-user-select"
        >
          <option value="">Select investor...</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Portfolio
        <select
          value={selectedPortfolioId}
          onChange={(e) => onPortfolioChange(e.target.value)}
          data-testid="invest-portfolio-select"
        >
          <option value="">Select portfolio...</option>
          {portfolios.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>

      <div className="invest-context-create">
        <input
          placeholder="New portfolio name"
          value={newPortfolioName}
          onChange={(e) => onNewPortfolioNameChange(e.target.value)}
          data-testid="invest-new-portfolio-name"
        />
        <button
          type="button"
          onClick={onCreatePortfolio}
          disabled={!selectedUserId || !newPortfolioName.trim()}
          data-testid="invest-create-portfolio-btn"
        >
          Create
        </button>
      </div>
    </div>
  )
}
