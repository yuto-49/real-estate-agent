import { useState } from 'react'
import { parseHoldingsCsv, type CsvFormat } from '../../utils/csvImport'
import type { PortfolioHoldingCreate } from '../../utils/types'

interface CsvImportPanelProps {
  onImport: (holdings: PortfolioHoldingCreate[]) => Promise<void>
}

const FORMAT_LABELS: Record<CsvFormat, string> = {
  stessa: 'Stessa export',
  reihub: 'REI Hub export',
  generic: 'generic CSV',
}

/**
 * CSV import for holdings. Auto-detects Stessa / REI Hub exports, then shows
 * the parsed rows as an editable table so the investor can override any
 * value before committing the import.
 */
export default function CsvImportPanel({ onImport }: CsvImportPanelProps) {
  const [format, setFormat] = useState<CsvFormat | null>(null)
  const [rows, setRows] = useState<PortfolioHoldingCreate[]>([])
  const [errors, setErrors] = useState<string[]>([])
  const [importing, setImporting] = useState(false)

  const handleFile = async (file: File) => {
    const text = await file.text()
    const result = parseHoldingsCsv(text)
    setFormat(result.format)
    setRows(result.holdings)
    setErrors(result.errors)
  }

  const updateRow = (index: number, patch: Partial<PortfolioHoldingCreate>) => {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  }

  const updateRent = (index: number, value: string) => {
    const rent = value === '' ? null : Number(value)
    setRows((prev) =>
      prev.map((row, i) =>
        i === index
          ? { ...row, financials: { ...(row.financials ?? {}), monthly_rent: rent } }
          : row,
      ),
    )
  }

  const handleImport = async () => {
    if (rows.length === 0) return
    setImporting(true)
    try {
      await onImport(rows)
      setRows([])
      setFormat(null)
      setErrors([])
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="csv-import-panel" data-testid="csv-import-panel">
      <label className="csv-import-label">
        Import holdings from CSV (Stessa / REI Hub)
        <input
          type="file"
          accept=".csv,text/csv"
          data-testid="csv-file-input"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void handleFile(file)
          }}
        />
      </label>

      {format && (
        <p className="csv-import-format" data-testid="csv-format">
          Detected: <strong>{FORMAT_LABELS[format]}</strong> — {rows.length} holding(s) ready.
          Review and override any value before importing.
        </p>
      )}

      {errors.length > 0 && (
        <ul className="csv-import-errors">
          {errors.map((err) => (
            <li key={err}>{err}</li>
          ))}
        </ul>
      )}

      {rows.length > 0 && (
        <>
          <table className="csv-import-table">
            <thead>
              <tr>
                <th>Address</th>
                <th>Zip</th>
                <th>Asset class</th>
                <th>Monthly rent</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.address}-${index}`}>
                  <td>
                    <input
                      value={row.address}
                      onChange={(e) => updateRow(index, { address: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={row.zip_code ?? ''}
                      onChange={(e) => updateRow(index, { zip_code: e.target.value || null })}
                    />
                  </td>
                  <td>
                    <input
                      value={row.asset_class ?? 'sfr'}
                      onChange={(e) => updateRow(index, { asset_class: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      value={row.financials?.monthly_rent ?? ''}
                      onChange={(e) => updateRent(index, e.target.value)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            type="button"
            disabled={importing}
            onClick={() => void handleImport()}
            data-testid="csv-import-confirm"
          >
            {importing ? 'Importing…' : `Import ${rows.length} holding(s)`}
          </button>
        </>
      )}
    </div>
  )
}
