/**
 * Shared JP currency and percentage formatters.
 *
 * Smart 万円/億円 formatting for Tokyo brokerage UI.
 */

/** Format JPY with smart 万円/億円 units. */
export function formatYen(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value >= 100_000_000) return `¥${(value / 100_000_000).toFixed(1)}億`
  if (value >= 10_000) return `¥${(value / 10_000).toLocaleString('ja-JP', { maximumFractionDigits: 0 })}万`
  return `¥${value.toLocaleString('ja-JP')}`
}

/** Format JPY using Intl (no unit shortening). */
export function formatMoney(value: number | null | undefined): string {
  if (value == null) return '—'
  return value.toLocaleString('ja-JP', {
    style: 'currency',
    currency: 'JPY',
    maximumFractionDigits: 0,
  })
}

/** Format decimal as percentage (e.g. 0.045 → "4.5%"). */
export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value == null) return '—'
  return `${(value * 100).toFixed(digits)}%`
}
