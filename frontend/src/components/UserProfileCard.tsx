import type { UserProfile } from '../utils/types'
import {
  formatJpyCompact,
  formatLifeStageLabel,
  formatRiskToleranceLabel,
  formatSearchRadius,
  formatUserRoleLabel,
} from '../utils/japan'

function formatBudget(min: number | null | undefined, max: number | null | undefined): string {
  return `${formatJpyCompact(min)} - ${formatJpyCompact(max)}`
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
                <button className="icon-btn" onClick={onEdit} title="プロフィールを編集">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
              )}
              {onDelete && (
                <button className="icon-btn icon-btn-danger" onClick={onDelete} title="プロフィールを削除">
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
          <label>利用区分</label>
          <p>{formatUserRoleLabel(user.role)}</p>
        </div>
        <div>
          <label>予算帯</label>
          <p>{formatBudget(user.budget_min, user.budget_max)}</p>
        </div>
        <div>
          <label>検討期間</label>
          <p>{user.timeline_days ? `${user.timeline_days} 日` : '—'}</p>
        </div>
        <div>
          <label>リスク許容度</label>
          <p>{formatRiskToleranceLabel(user.risk_tolerance)}</p>
        </div>
        <div>
          <label>対象エリア</label>
          <p>
            {user.zip_code ? `〒${user.zip_code}` : '—'}
            {user.search_radius ? `（${formatSearchRadius(user.search_radius)}）` : ''}
          </p>
        </div>
        <div>
          <label>希望物件種別</label>
          <p>{user.preferred_types.length ? user.preferred_types.join(', ') : '—'}</p>
        </div>
        <div>
          <label>運用フェーズ</label>
          <p>{formatLifeStageLabel(user.life_stage)}</p>
        </div>
      </div>
    </div>
  )
}
