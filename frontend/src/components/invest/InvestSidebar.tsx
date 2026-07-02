export type InvestSection = 'dashboard' | 'portfolio' | 'analysis' | 'simulation' | 'strategy'

interface InvestSidebarProps {
  active: InvestSection
  onChange: (section: InvestSection) => void
}

const SECTIONS: Array<{ key: InvestSection; label: string; icon: string }> = [
  { key: 'dashboard', label: 'ダッシュボード', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4' },
  { key: 'portfolio', label: 'ポートフォリオ', icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10' },
  { key: 'analysis', label: '分析', icon: 'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { key: 'simulation', label: 'シミュレーション', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
  { key: 'strategy', label: '戦略', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
]

export default function InvestSidebar({ active, onChange }: InvestSidebarProps) {
  return (
    <nav className="invest-sidebar" data-testid="invest-sidebar">
      <div className="invest-sidebar-label">ワークスペース</div>
      {SECTIONS.map((s) => (
        <button
          key={s.key}
          type="button"
          className={`invest-sidebar-item${active === s.key ? ' active' : ''}`}
          onClick={() => onChange(s.key)}
          data-testid={`invest-nav-${s.key}`}
        >
          <svg
            className="invest-sidebar-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d={s.icon} />
          </svg>
          {s.label}
        </button>
      ))}
    </nav>
  )
}
