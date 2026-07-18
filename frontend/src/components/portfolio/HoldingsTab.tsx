import { useCallback, useEffect, useState } from 'react'
import { api } from '../../utils/api'
import type {
  PortfolioAggregate,
  PortfolioHolding,
  PortfolioHoldingCreate,
} from '../../utils/types'
import { formatAssetClassLabel, formatJpyCompact } from '../../utils/japan'
import CsvImportPanel from './CsvImportPanel'

interface HoldingsTabProps {
  portfolioId: string
}

const EMPTY_HOLDING: PortfolioHoldingCreate = {
  address: '',
  asset_class: 'sfr',
  status: 'held',
  zip_code: '',
}

export default function HoldingsTab({ portfolioId }: HoldingsTabProps) {
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([])
  const [aggregate, setAggregate] = useState<PortfolioAggregate | null>(null)
  const [draft, setDraft] = useState<PortfolioHoldingCreate>(EMPTY_HOLDING)
  const [listingUrl, setListingUrl] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

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
      setError(err instanceof Error ? err.message : '保有物件を取得できませんでした。')
    } finally {
      setLoading(false)
    }
  }, [portfolioId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const addHolding = async () => {
    if (!draft.address.trim()) {
      setError('所在地は必須です。')
      return
    }
    try {
      await api.portfolio.addHolding(portfolioId, draft)
      setDraft(EMPTY_HOLDING)
      setListingUrl('')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : '保有物件を追加できませんでした。')
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
        zip_code: parsed.zip_code ?? prev.zip_code,
        property_id: prev.property_id,
      }))
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '掲載URLから物件情報を読み取れませんでした。')
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
          <div><span>保有件数</span><strong>{aggregate.holding_count}</strong></div>
          <div><span>資産総額</span><strong>{formatJpyCompact(aggregate.total_value)}</strong></div>
          <div><span>純資産</span><strong>{formatJpyCompact(aggregate.total_equity)}</strong></div>
          <div><span>月次キャッシュフロー</span><strong>{formatJpyCompact(aggregate.monthly_cash_flow)}</strong></div>
          <div><span>加重平均利回り</span><strong>{(aggregate.blended_cap_rate * 100).toFixed(2)}%</strong></div>
          <div>
            <span>加重平均 DSCR</span>
            <strong>{aggregate.weighted_dscr ? aggregate.weighted_dscr.toFixed(2) : '—'}</strong>
          </div>
        </section>
      )}

      <section className="portfolio-add-holding">
        <h3>保有物件を追加</h3>
        <div className="listing-import-row">
          <input
            placeholder="REINS / SUUMO / at home の掲載URL（任意）"
            value={listingUrl}
            onChange={(e) => setListingUrl(e.target.value)}
          />
          <button type="button" onClick={() => void prefillFromListing()}>
            掲載情報を反映
          </button>
        </div>
        <div className="portfolio-form-grid">
          <input
            placeholder="所在地（都道府県・市区町村・町名・番地）"
            value={draft.address}
            onChange={(e) => setDraft({ ...draft, address: e.target.value })}
            data-testid="holding-address"
          />
          <input
            placeholder="郵便番号"
            value={draft.zip_code ?? ''}
            onChange={(e) => setDraft({ ...draft, zip_code: e.target.value })}
          />
          <select
            value={draft.asset_class ?? 'sfr'}
            onChange={(e) => setDraft({ ...draft, asset_class: e.target.value })}
          >
            <option value="sfr">戸建て</option>
            <option value="mf_2_4">小規模一棟</option>
            <option value="mf_5_plus">一棟マンション</option>
            <option value="condo">区分マンション</option>
            <option value="townhouse">テラスハウス</option>
          </select>
          <input
            type="number"
            placeholder="月額賃料"
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
          追加する
        </button>
      </section>

      <CsvImportPanel onImport={importCsv} />

      <section className="portfolio-holdings-list">
        <h3>保有物件一覧</h3>
        {loading && <p>読み込み中…</p>}
        {!loading && holdings.length === 0 && <p>保有物件はまだ登録されていません。</p>}
        <ul>
          {holdings.map((h) => (
            <li key={h.id} data-testid="holding-row">
              <div>
                <strong>{h.address}</strong>
                <span className="holding-meta">
                  {formatAssetClassLabel(h.asset_class)} ・ {h.zip_code ? `〒${h.zip_code}` : '郵便番号未設定'} ・
                  月額賃料 {formatJpyCompact(h.financials?.monthly_rent)}
                </span>
              </div>
              <button type="button" onClick={() => void removeHolding(h.id)}>
                削除
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
