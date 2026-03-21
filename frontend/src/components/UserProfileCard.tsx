import type { UserProfile } from '../utils/types'

function formatCurrency(value: number | null | undefined): string {
  return typeof value === 'number' ? `$${value.toLocaleString()}` : 'N/A'
}

interface Props {
  user: UserProfile
  onEdit?: () => void
  onDelete?: () => void
}

export default function UserProfileCard({ user, onEdit, onDelete }: Props) {
  return (
    <div className="user-detail">
      <div className="user-detail-header">
        <div className="user-detail-title-row">
          <div>
            <h3>{user.name}</h3>
            <p>{user.email}</p>
          </div>
          {(onEdit || onDelete) && (
            <div className="user-detail-actions">
              {onEdit && (
                <button className="icon-btn" onClick={onEdit} title="Edit profile">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
              )}
              {onDelete && (
                <button className="icon-btn icon-btn-danger" onClick={onDelete} title="Delete user">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
                    <path d="M10 11v6M14 11v6"/>
                    <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/>
                  </svg>
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="user-meta-grid">
        <div>
          <label>Role</label>
          <p>{user.role}</p>
        </div>
        <div>
          <label>Budget</label>
          <p>{formatCurrency(user.budget_min)} - {formatCurrency(user.budget_max)}</p>
        </div>
        <div>
          <label>Timeline</label>
          <p>{user.timeline_days ?? 'N/A'} days</p>
        </div>
        <div>
          <label>Risk Tolerance</label>
          <p>{user.risk_tolerance || 'N/A'}</p>
        </div>
        <div>
          <label>Location</label>
          <p>
            {user.zip_code || 'N/A'}
            {user.search_radius ? ` (${user.search_radius} mi radius)` : ''}
          </p>
        </div>
        <div>
          <label>Preferred Types</label>
          <p>{user.preferred_types.length ? user.preferred_types.join(', ') : 'N/A'}</p>
        </div>
      </div>
    </div>
  )
}
