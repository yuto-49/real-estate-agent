import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import CsvImportPanel from './CsvImportPanel'

function makeCsvFile(contents: string): File {
  return new File([contents], 'holdings.csv', { type: 'text/csv' })
}

describe('CsvImportPanel', () => {
  it('detects format and shows editable rows after upload', async () => {
    const onImport = vi.fn().mockResolvedValue(undefined)
    render(<CsvImportPanel onImport={onImport} />)

    const csv = [
      'Address,Zip Code,Market Value,Monthly Rent',
      '123 Main St,60615,310000,2400',
    ].join('\n')

    fireEvent.change(screen.getByTestId('csv-file-input'), {
      target: { files: [makeCsvFile(csv)] },
    })

    await waitFor(() => {
      expect(screen.getByTestId('csv-format')).toHaveTextContent('Stessa 形式')
    })
    expect(screen.getByDisplayValue('123 Main St')).toBeInTheDocument()
    expect(screen.getByDisplayValue('戸建て')).toBeInTheDocument()
  })

  it('passes edited rows to onImport on confirm', async () => {
    const onImport = vi.fn().mockResolvedValue(undefined)
    render(<CsvImportPanel onImport={onImport} />)

    const csv = ['Address,Monthly Rent', '456 Oak Ave,1800'].join('\n')
    fireEvent.change(screen.getByTestId('csv-file-input'), {
      target: { files: [makeCsvFile(csv)] },
    })

    await waitFor(() => screen.getByTestId('csv-import-confirm'))

    const addressInput = screen.getByDisplayValue('456 Oak Ave')
    fireEvent.change(addressInput, { target: { value: '456 Oak Avenue' } })
    fireEvent.click(screen.getByTestId('csv-import-confirm'))

    await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1))
    const rows = onImport.mock.calls[0][0]
    expect(rows[0].address).toBe('456 Oak Avenue')
  })
})
