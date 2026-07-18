import { describe, expect, it } from 'vitest'
import { formatMoney, formatNumber, formatPercent, formatYen } from './format'

describe('formatYen', () => {
  it('formats null/undefined as an em dash', () => {
    expect(formatYen(null)).toBe('—')
    expect(formatYen(undefined)).toBe('—')
  })

  it('formats zero', () => {
    expect(formatYen(0)).toBe('¥0')
  })

  it('formats sub-man values with a yen sign', () => {
    expect(formatYen(4_200)).toBe('¥4,200')
    expect(formatYen(9_999)).toBe('¥9,999')
  })

  it('formats the exact 1-man boundary (10,000)', () => {
    expect(formatYen(10_000)).toBe('1万円')
  })

  it('formats man-scale values with thousands separators', () => {
    expect(formatYen(12_340_000)).toBe('1,234万円')
  })

  it('preserves precision for partial man values', () => {
    expect(formatYen(15_000)).toBe('1.5万円')
    expect(formatYen(12_500)).toBe('1.25万円')
  })

  it('does not round sub-oku values up into 1 oku', () => {
    expect(formatYen(99_999_999)).toBe('9,999.99万円')
  })

  it('formats the exact 1-oku boundary (100,000,000)', () => {
    expect(formatYen(100_000_000)).toBe('1億円')
  })

  it('formats oku-scale values with two decimal places', () => {
    expect(formatYen(123_000_000)).toBe('1.23億円')
  })

  it('drops trailing zeros for oku-scale values', () => {
    expect(formatYen(150_000_000)).toBe('1.5億円')
  })

  it('does not round sub-next-oku values up', () => {
    expect(formatYen(199_999_999)).toBe('1.99億円')
  })

  it('formats negative values with a leading minus sign', () => {
    expect(formatYen(-12_340_000)).toBe('-1,234万円')
    expect(formatYen(-15_000)).toBe('-1.5万円')
    expect(formatYen(-4_200)).toBe('-¥4,200')
    expect(formatYen(-100_000_000)).toBe('-1億円')
  })
})

describe('formatMoney', () => {
  it('formats null/undefined as an em dash', () => {
    expect(formatMoney(null)).toBe('—')
    expect(formatMoney(undefined)).toBe('—')
  })

  it('formats a whole-yen currency string', () => {
    expect(formatMoney(1_234)).toBe('¥1,234')
  })

  it('formats zero', () => {
    expect(formatMoney(0)).toBe('¥0')
  })

  it('formats negative values', () => {
    expect(formatMoney(-1_234)).toBe('-¥1,234')
  })
})

describe('formatPercent', () => {
  it('formats null/undefined as an em dash', () => {
    expect(formatPercent(null)).toBe('—')
    expect(formatPercent(undefined)).toBe('—')
  })

  it('formats a decimal fraction as a percent with 2 digits by default', () => {
    expect(formatPercent(0.042)).toBe('4.20%')
  })

  it('honors a custom digits argument', () => {
    expect(formatPercent(0.0421, 1)).toBe('4.2%')
    expect(formatPercent(0.05, 0)).toBe('5%')
  })

  it('formats negative values', () => {
    expect(formatPercent(-0.05)).toBe('-5.00%')
  })
})

describe('formatNumber', () => {
  it('formats null/undefined as an em dash', () => {
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber(undefined)).toBe('—')
  })

  it('formats a plain number with thousands separators', () => {
    expect(formatNumber(12_345)).toBe('12,345')
  })

  it('formats zero and negative numbers', () => {
    expect(formatNumber(0)).toBe('0')
    expect(formatNumber(-12_345)).toBe('-12,345')
  })
})
