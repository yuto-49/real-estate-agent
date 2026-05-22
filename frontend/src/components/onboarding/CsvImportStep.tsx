import { useEffect, useState } from 'react'

import CsvImportPanel from '../portfolio/CsvImportPanel'
import { useAuth } from '../../hooks/useAuth'
import { api } from '../../utils/api'
import type { PortfolioHoldingCreate } from '../../utils/types'

interface CsvImportStepProps {
  onImported: (portfolioId: string, summary: { inserted: number; updated: number }) => void
}

/**
 * Wraps the existing CsvImportPanel for the onboarding wizard. The panel
 * itself handles parsing + preview; this component owns the network call to
 * /api/portfolio/import/csv and wizard navigation on success.
 */
export default function CsvImportStep({ onImported }: CsvImportStepProps) {
  const { user } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [template, setTemplate] = useState<{ columns: string[]; csv: string } | null>(null)

  useEffect(() => {
    let cancelled = false
    void api.portfolio
      .csvTemplate()
      .then((t) => {
        if (!cancelled) setTemplate(t)
      })
      .catch(() => {
        if (!cancelled) setTemplate(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleImport = async (holdings: PortfolioHoldingCreate[]) => {
    setError(null)
    if (!user?.id) {
      setError('You must be signed in to import a portfolio.')
      return
    }
    if (holdings.length === 0) return

    try {
      const result = await api.portfolio.importCsv({
        user_id: user.id,
        user_email: user.email,
        holdings,
      })
      onImported(result.portfolio_id, {
        inserted: result.inserted_count,
        updated: result.updated_count,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Import failed'
      setError(message)
    }
  }

  const handleDownloadTemplate = () => {
    if (!template) return
    const blob = new Blob([template.csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'portfolio-template.csv'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="onboarding-csv-step" data-testid="onboarding-csv-step">
      <h3>Upload your portfolio CSV</h3>
      <p className="onboarding-subtle">
        Drop a Stessa, REI Hub, or generic export. We'll parse the columns,
        let you review each row, and then create your portfolio.
      </p>

      <button
        type="button"
        className="onboarding-secondary"
        onClick={handleDownloadTemplate}
        disabled={!template}
        data-testid="csv-template-download"
      >
        Download CSV template
      </button>

      <CsvImportPanel onImport={handleImport} />

      {error && (
        <p className="onboarding-error" data-testid="csv-import-error">
          {error}
        </p>
      )}
    </div>
  )
}
