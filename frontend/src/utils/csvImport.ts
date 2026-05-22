/**
 * CSV import for investor portfolios — Phase P6.
 *
 * Auto-detects exports from Stessa and REI Hub (the two most common rental
 * bookkeeping tools individual investors already use) and normalizes them
 * into `PortfolioHoldingCreate` rows. Unknown layouts fall back to `generic`
 * and are still parsed on a best-effort basis off an `address` column.
 *
 * The parser is intentionally dependency-free so it can be unit-tested in
 * isolation and run in the browser without a CSV library.
 */
import type { PortfolioHoldingCreate } from './types'

export type CsvFormat = 'stessa' | 'reihub' | 'generic'

export interface CsvImportResult {
  format: CsvFormat
  holdings: PortfolioHoldingCreate[]
  errors: string[]
  rowCount: number
}

/** Split a single CSV line, honoring double-quoted fields and escaped quotes. */
export function parseCsvLine(line: string): string[] {
  const fields: string[] = []
  let current = ''
  let inQuotes = false

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i]
    if (inQuotes) {
      if (char === '"') {
        if (line[i + 1] === '"') {
          current += '"'
          i += 1
        } else {
          inQuotes = false
        }
      } else {
        current += char
      }
    } else if (char === '"') {
      inQuotes = true
    } else if (char === ',') {
      fields.push(current)
      current = ''
    } else {
      current += char
    }
  }
  fields.push(current)
  return fields.map((f) => f.trim())
}

const normalize = (header: string): string =>
  header.toLowerCase().replace(/[_\s]+/g, ' ').trim()

/**
 * Header aliases → canonical holding fields. Covers Stessa and REI Hub column
 * names plus common generic spellings. A few money columns are format-specific
 * (Stessa "market value" vs REI Hub "estimated value") but all are listed here
 * so a single pass handles every layout.
 */
const COLUMN_ALIASES: Record<string, keyof FlatHolding> = {
  address: 'address',
  property: 'address',
  'property name': 'address',
  'property address': 'address',
  zip: 'zip_code',
  'zip code': 'zip_code',
  zipcode: 'zip_code',
  'postal code': 'zip_code',
  'asset class': 'asset_class',
  'property type': 'asset_class',
  type: 'asset_class',
  'purchase price': 'cost_basis',
  'cost basis': 'cost_basis',
  'acquisition price': 'cost_basis',
  'market value': 'current_value_estimate',
  'estimated value': 'current_value_estimate',
  'current value': 'current_value_estimate',
  'mortgage balance': 'loan_balance',
  'loan balance': 'loan_balance',
  'outstanding loan': 'loan_balance',
  'interest rate': 'interest_rate',
  rate: 'interest_rate',
  'monthly rent': 'monthly_rent',
  rent: 'monthly_rent',
  'gross rent': 'monthly_rent',
  'monthly piti': 'monthly_piti',
  piti: 'monthly_piti',
}

interface FlatHolding {
  address: string
  zip_code: string
  asset_class: string
  cost_basis: string
  current_value_estimate: string
  loan_balance: string
  interest_rate: string
  monthly_rent: string
  monthly_piti: string
}

const FINANCIAL_FIELDS = [
  'cost_basis',
  'current_value_estimate',
  'loan_balance',
  'interest_rate',
  'monthly_rent',
  'monthly_piti',
] as const

const ASSET_CLASS_ALIASES: Record<string, string> = {
  'single family': 'sfr',
  'single-family': 'sfr',
  sfr: 'sfr',
  condo: 'condo',
  townhouse: 'townhouse',
  townhome: 'townhouse',
  duplex: 'mf_2_4',
  triplex: 'mf_2_4',
  fourplex: 'mf_2_4',
  '2-4 unit': 'mf_2_4',
  multifamily: 'mf_5_plus',
  'multi-family': 'mf_5_plus',
}

/** Detect the export tool from the header row. */
export function detectCsvFormat(headers: string[]): CsvFormat {
  const normalized = new Set(headers.map(normalize))
  if (normalized.has('market value') || normalized.has('mortgage balance')) {
    return 'stessa'
  }
  if (normalized.has('loan balance') || normalized.has('estimated value')) {
    return 'reihub'
  }
  return 'generic'
}

/** Parse a percent-or-decimal rate string into a decimal fraction (6.5 → 0.065). */
function parseRate(raw: string): number | null {
  const value = parseMoney(raw)
  if (value === null) return null
  return value > 1 ? value / 100 : value
}

/** Strip $, commas, % and parse a numeric string. Returns null when unparseable. */
function parseMoney(raw: string): number | null {
  const cleaned = raw.replace(/[$,%\s]/g, '')
  if (cleaned === '') return null
  const value = Number(cleaned)
  return Number.isFinite(value) ? value : null
}

/**
 * Parse a holdings CSV. Returns the detected format, normalized holdings, and a
 * list of per-row errors (rows missing an address are skipped, not fatal).
 */
export function parseHoldingsCsv(text: string): CsvImportResult {
  const lines = text
    .split(/\r?\n/)
    .filter((line) => line.trim() !== '')

  if (lines.length === 0) {
    return { format: 'generic', holdings: [], errors: ['CSV is empty.'], rowCount: 0 }
  }

  const headers = parseCsvLine(lines[0])
  const format = detectCsvFormat(headers)

  const columnMap = headers.map((h) => COLUMN_ALIASES[normalize(h)] ?? null)
  if (!columnMap.includes('address')) {
    return {
      format,
      holdings: [],
      errors: ['No recognizable "address" column found in CSV header.'],
      rowCount: lines.length - 1,
    }
  }

  const holdings: PortfolioHoldingCreate[] = []
  const errors: string[] = []

  for (let row = 1; row < lines.length; row += 1) {
    const cells = parseCsvLine(lines[row])
    const flat: Partial<FlatHolding> = {}
    columnMap.forEach((field, col) => {
      if (field && cells[col] !== undefined && cells[col] !== '') {
        flat[field] = cells[col]
      }
    })

    if (!flat.address) {
      errors.push(`Row ${row + 1}: missing address — skipped.`)
      continue
    }

    const financials: PortfolioHoldingCreate['financials'] = {}
    if (flat.cost_basis) financials.cost_basis = parseMoney(flat.cost_basis)
    if (flat.current_value_estimate) {
      financials.current_value_estimate = parseMoney(flat.current_value_estimate)
      financials.value_estimate_source = format
    }
    if (flat.loan_balance) financials.loan_balance = parseMoney(flat.loan_balance)
    if (flat.interest_rate) financials.interest_rate = parseRate(flat.interest_rate)
    if (flat.monthly_rent) financials.monthly_rent = parseMoney(flat.monthly_rent)
    if (flat.monthly_piti) financials.monthly_piti = parseMoney(flat.monthly_piti)

    const hasFinancials = FINANCIAL_FIELDS.some(
      (f) => financials[f] !== undefined && financials[f] !== null,
    )

    const assetClass = flat.asset_class
      ? ASSET_CLASS_ALIASES[normalize(flat.asset_class)] ?? 'sfr'
      : 'sfr'

    holdings.push({
      address: flat.address,
      zip_code: flat.zip_code ?? null,
      asset_class: assetClass,
      status: 'held',
      financials: hasFinancials ? financials : null,
    })
  }

  return { format, holdings, errors, rowCount: lines.length - 1 }
}
