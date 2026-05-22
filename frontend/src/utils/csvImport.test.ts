import { describe, expect, it } from 'vitest'
import { detectCsvFormat, parseCsvLine, parseHoldingsCsv } from './csvImport'

describe('parseCsvLine', () => {
  it('splits simple comma-separated fields', () => {
    expect(parseCsvLine('a,b,c')).toEqual(['a', 'b', 'c'])
  })

  it('honors quoted fields containing commas', () => {
    expect(parseCsvLine('"123 Main St, Apt 4",60615')).toEqual([
      '123 Main St, Apt 4',
      '60615',
    ])
  })

  it('handles escaped quotes inside quoted fields', () => {
    expect(parseCsvLine('"she said ""hi""",x')).toEqual(['she said "hi"', 'x'])
  })
})

describe('detectCsvFormat', () => {
  it('detects Stessa exports by market value / mortgage balance columns', () => {
    expect(detectCsvFormat(['Address', 'Market Value', 'Monthly Rent'])).toBe('stessa')
    expect(detectCsvFormat(['Property', 'Mortgage Balance'])).toBe('stessa')
  })

  it('detects REI Hub exports by loan balance / estimated value columns', () => {
    expect(detectCsvFormat(['Address', 'Loan Balance', 'Rent'])).toBe('reihub')
    expect(detectCsvFormat(['Property Name', 'Estimated Value'])).toBe('reihub')
  })

  it('falls back to generic for unknown layouts', () => {
    expect(detectCsvFormat(['Address', 'Notes'])).toBe('generic')
  })
})

describe('parseHoldingsCsv', () => {
  it('parses a Stessa-style export and normalizes financials', () => {
    const csv = [
      'Address,Zip Code,Property Type,Purchase Price,Market Value,Mortgage Balance,Interest Rate,Monthly Rent',
      '"123 Main St, Chicago, IL",60615,Single Family,$250000,"$310,000","$190,000",6.5%,"$2,400"',
    ].join('\n')

    const result = parseHoldingsCsv(csv)

    expect(result.format).toBe('stessa')
    expect(result.errors).toEqual([])
    expect(result.holdings).toHaveLength(1)

    const [holding] = result.holdings
    expect(holding.address).toBe('123 Main St, Chicago, IL')
    expect(holding.zip_code).toBe('60615')
    expect(holding.asset_class).toBe('sfr')
    expect(holding.financials?.cost_basis).toBe(250000)
    expect(holding.financials?.current_value_estimate).toBe(310000)
    expect(holding.financials?.loan_balance).toBe(190000)
    // 6.5% must normalize to a decimal fraction.
    expect(holding.financials?.interest_rate).toBeCloseTo(0.065)
    expect(holding.financials?.monthly_rent).toBe(2400)
    expect(holding.financials?.value_estimate_source).toBe('stessa')
  })

  it('parses a REI Hub-style export', () => {
    const csv = [
      'Property,Zip,Loan Balance,Rent',
      '456 Oak Ave,60640,150000,1800',
    ].join('\n')

    const result = parseHoldingsCsv(csv)
    expect(result.format).toBe('reihub')
    expect(result.holdings[0].address).toBe('456 Oak Ave')
    expect(result.holdings[0].financials?.loan_balance).toBe(150000)
    expect(result.holdings[0].financials?.monthly_rent).toBe(1800)
  })

  it('reports an error row for missing address but keeps valid rows', () => {
    const csv = [
      'Address,Monthly Rent',
      ',1200',
      '789 Pine Rd,1500',
    ].join('\n')

    const result = parseHoldingsCsv(csv)
    expect(result.holdings).toHaveLength(1)
    expect(result.holdings[0].address).toBe('789 Pine Rd')
    expect(result.errors).toHaveLength(1)
    expect(result.errors[0]).toContain('Row 2')
  })

  it('returns a fatal error when no address column is present', () => {
    const result = parseHoldingsCsv('Notes,Rent\nfoo,1200')
    expect(result.holdings).toEqual([])
    expect(result.errors[0]).toContain('address')
  })

  it('handles an empty CSV gracefully', () => {
    const result = parseHoldingsCsv('')
    expect(result.holdings).toEqual([])
    expect(result.errors[0]).toContain('empty')
  })

  it('leaves financials null when no financial columns are present', () => {
    const result = parseHoldingsCsv('Address\n100 First St')
    expect(result.holdings[0].financials).toBeNull()
  })
})
