/**
 * Single money-formatting layer for the JP-only investor UI. All JPY display
 * anywhere in the frontend should go through these helpers rather than
 * hand-rolled `toLocaleString` / `$` string interpolation.
 */

const HUNDRED_MILLION = 100_000_000 // 1億
const TEN_THOUSAND = 10_000 // 1万
const UNIT_DECIMAL_DIGITS = 2
const JPY_CURRENCY_FORMATTER = new Intl.NumberFormat('ja-JP', {
  style: 'currency',
  currency: 'JPY',
  maximumFractionDigits: 0,
})
const JPY_UNIT_FORMATTER = new Intl.NumberFormat('ja-JP', {
  maximumFractionDigits: UNIT_DECIMAL_DIGITS,
})

function truncateToDigits(value: number, digits: number): number {
  const scale = 10 ** digits
  return Math.trunc(value * scale) / scale
}

/**
 * Smart Japanese-unit currency formatting, e.g.:
 *   150_000_000 -> "1.5億円"
 *   12_340_000  -> "1,234万円"
 *   4_200       -> "¥4,200"
 */
export function formatYen(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'

  const sign = value < 0 ? '-' : ''
  const abs = Math.abs(value)

  if (abs >= HUNDRED_MILLION) {
    const oku = truncateToDigits(abs / HUNDRED_MILLION, UNIT_DECIMAL_DIGITS)
    return `${sign}${JPY_UNIT_FORMATTER.format(oku)}億円`
  }

  if (abs >= TEN_THOUSAND) {
    const man = truncateToDigits(abs / TEN_THOUSAND, UNIT_DECIMAL_DIGITS)
    return `${sign}${JPY_UNIT_FORMATTER.format(man)}万円`
  }

  return `${sign}¥${Math.round(abs).toLocaleString('ja-JP')}`
}

/**
 * Plain Intl currency formatting, e.g. "¥1,234". Prefer `formatYen` for
 * investor-facing large sums; use this where an unrounded, locale-standard
 * currency string is wanted instead.
 */
export function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return JPY_CURRENCY_FORMATTER.formatToParts(value)
    .map((part) => (part.type === 'currency' ? '¥' : part.value))
    .join('')
}

/** e.g. formatPercent(0.042) -> "4.20%" */
export function formatPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

/** Locale-formatted plain number, e.g. formatNumber(12345) -> "12,345" */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('ja-JP').format(value)
}
