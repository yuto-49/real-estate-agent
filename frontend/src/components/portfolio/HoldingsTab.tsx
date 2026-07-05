import { useCallback, useEffect, useState } from 'react'
import { api } from '../../utils/api'
import type {
  PortfolioAggregate,
  PortfolioHolding,
  PortfolioHoldingCreate,
} from '../../utils/types'
import CsvImportPanel from './CsvImportPanel'
import RentComps from '../RentComps'

interface HoldingsTabProps {
  portfolioId: string
}

const EMPTY_HOLDING: PortfolioHoldingCreate = {
  address: '',
  asset_class: 'sfr',
  status: 'held',
  zip_code: '',
}

function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `¥${Math.round(value).toLocaleString()}`
}

export default function HoldingsTab({ portfolioId }: HoldingsTabProps) {
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([])
  const [aggregate, setAggregate] = useState<PortfolioAggregate | null>(null)
  const [draft, setDraft] = useState<PortfolioHoldingCreate>(EMPTY_HOLDING)
  const [listingUrl, setListingUrl] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [expandedRentComps, setExpandedRentComps] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [h, agg] = await Promise.all([
        api.portfolio.listHoldings(portfolioId),
        api.portfolio.aggregate(portfolioId),
      ])
      setHoldings(h)
      setAggregate(agg)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load holdings')
    } finally {
      setLoading(false)
    }
  }, [portfolioId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const addHolding = async () => {
    if (!draft.address.trim()) {
      setError('Address is required.')
      return
    }
    try {
      await api.portfolio.addHolding(portfolioId, draft)
      setDraft(EMPTY_HOLDING)
      setListingUrl('')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add holding')
    }
  }

  const prefillFromListing = async () => {
    if (!listingUrl.trim()) return
    try {
      const parsed = await api.listing.parse(listingUrl)
      // Listing import only seeds the form — the investor still overrides.
      setDraft((prev) => ({
        ...prev,
        address: parsed.address_hint || prev.address,
        zip_code: parsed.postal_code ?? prev.zip_code,
        property_id: prev.property_id,
      }))
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not parse listing URL')
    }
  }

  const importCsv = async (rows: PortfolioHoldingCreate[]) => {
    for (const row of rows) {
      await api.portfolio.addHolding(portfolioId, row)
    }
    await refresh()
  }

  const removeHolding = async (holdingId: string) => {
    await api.portfolio.deleteHolding(portfolioId, holdingId)
    await refresh()
  }

  return (
    <div className="portfolio-tab" data-testid="holdings-tab">
      {error && <p className="portfolio-error">{error}</p>}

      {aggregate && (
        <section className="portfolio-aggregate" data-testid="portfolio-aggregate">
          <div><span>物件数</span><strong>{aggregate.holding_count}</strong></div>
          <div><span>総資産額</span><strong>{formatMoney(aggregate.total_value)}</strong></div>
          <div><span>自己資本</span><strong>{formatMoney(aggregate.total_equity)}</strong></div>
          <div><span>月間キャッシュフロー</span><strong>{formatMoney(aggregate.monthly_cash_flow)}</strong></div>
          <div><span>加重キャップレート</span><strong>{(aggregate.blended_cap_rate * 100).toFixed(2)}%</strong></div>
          <div>
            <span>加重DSCR</span>
            <strong>{aggregate.weighted_dscr ? aggregate.weighted_dscr.toFixed(2) : '—'}</strong>
          </div>
        </section>
      )}

      <section className="portfolio-add-holding">
        <h3>Add a holding</h3>
        <div className="listing-import-row">
          <input
            placeholder="Suumo or REINFOLIB URL (optional)"
            value={listingUrl}
            onChange={(e) => setListingUrl(e.target.value)}
          />
          <button type="button" onClick={() => void prefillFromListing()}>
            Prefill from listing
          </button>
        </div>
        <div className="portfolio-form-grid">
          <input
            placeholder="Address"
            value={draft.address}
            onChange={(e) => setDraft({ ...draft, address: e.target.value })}
            data-testid="holding-address"
          />
          <input
            placeholder="Zip code"
            value={draft.zip_code ?? ''}
            onChange={(e) => setDraft({ ...draft, zip_code: e.target.value })}
          />
          <select
            value={draft.asset_class ?? 'sfr'}
            onChange={(e) => setDraft({ ...draft, asset_class: e.target.value })}
          >
            <option value="aparuto">アパート</option>
            <option value="mansion">マンション</option>
            <option value="ikkodate">一戸建て</option>
            <option value="one_room">ワンルーム</option>
          </select>
          <input
            type="number"
            placeholder="Monthly rent"
            value={draft.financials?.monthly_rent ?? ''}
            onChange={(e) =>
              setDraft({
                ...draft,
                financials: {
                  ...(draft.financials ?? {}),
                  monthly_rent: e.target.value === '' ? null : Number(e.target.value),
                },
              })
            }
          />
        </div>
        <button type="button" onClick={() => void addHolding()} data-testid="add-holding-btn">
          Add holding
        </button>
      </section>

      <CsvImportPanel onImport={importCsv} />

      <section className="portfolio-holdings-list">
        <h3>Holdings</h3>
        {loading && <p>Loading…</p>}
        {!loading && holdings.length === 0 && <p>No holdings yet.</p>}
        <ul>
          {holdings.map((h) => (
            <li key={h.id} data-testid="holding-row">
              <div>
                <strong>{h.address}</strong>
                <span className="holding-meta">
                  {h.asset_class} · {h.zip_code ?? 'no zip'} ·{' '}
                  rent {formatMoney(h.financials?.monthly_rent)}
                </span>
              </div>
              <div>
                {h.property_id && (
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedRentComps((prev) => (prev === h.id ? null : h.id))
                    }
                  >
                    {expandedRentComps === h.id ? 'Hide Comps' : 'Rent Comps'}
                  </button>
                )}
                <button type="button" onClick={() => void removeHolding(h.id)}>
                  Remove
                </button>
              </div>
              {expandedRentComps === h.id && h.property_id && (
                <RentComps propertyId={h.property_id} />
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
