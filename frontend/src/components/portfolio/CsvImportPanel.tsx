import { useState } from 'react'
import { parseHoldingsCsv, type CsvFormat } from '../../utils/csvImport'
import { formatAssetClassLabel } from '../../utils/japan'
import type { PortfolioHoldingCreate } from '../../utils/types'

interface CsvImportPanelProps {
  onImport: (holdings: PortfolioHoldingCreate[]) => Promise<void>
}

const FORMAT_LABELS: Record<CsvFormat, string> = {
  stessa: 'Stessa 形式',
  reihub: 'REI Hub 形式',
  generic: '汎用 CSV',
}

const ASSET_CLASS_OPTIONS = [
  'sfr',
  'mf_2_4',
  'mf_5_plus',
  'condo',
  'townhouse',
  'multifamily',
  'land',
] as const

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
        保有物件を CSV から取り込む
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
          検出形式: <strong>{FORMAT_LABELS[format]}</strong> ・ {rows.length} 件の物件を確認できます。
          取り込み前に内容を編集できます。
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
                <th>所在地</th>
                <th>郵便番号</th>
                <th>物件種別</th>
                <th>月額賃料</th>
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
                    <select
                      value={row.asset_class}
                      onChange={(e) => updateRow(index, { asset_class: e.target.value })}
                    >
                      {ASSET_CLASS_OPTIONS.map((assetClass) => (
                        <option key={assetClass} value={assetClass}>
                          {formatAssetClassLabel(assetClass)}
                        </option>
                      ))}
                    </select>
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
            {importing ? '取り込み中…' : `${rows.length} 件を取り込む`}
          </button>
        </>
      )}
    </div>
  )
}
