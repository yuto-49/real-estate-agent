import { useCallback, useEffect, useState } from 'react'
import { api } from '../utils/api'
import type { RentValidationResponse } from '../utils/types'

interface RentCompsProps {
  propertyId: string
}

function formatYen(value: number | null | undefined): string {
  if (value === null || value === undefined) return '\u2014'
  return `\u00a5${Math.round(value).toLocaleString()}`
}

type Verdict = 'aligned' | 'above_market' | 'below_market' | 'insufficient_data'

function verdictStyle(verdict: string): { bg: string; text: string; label: string } {
  switch (verdict as Verdict) {
    case 'aligned':
      return { bg: '#dcfce7', text: '#166534', label: 'Aligned' }
    case 'above_market':
      return { bg: '#fee2e2', text: '#991b1b', label: 'Above Market' }
    case 'below_market':
      return { bg: '#fef9c3', text: '#854d0e', label: 'Below Market' }
    case 'insufficient_data':
    default:
      return { bg: '#f3f4f6', text: '#374151', label: 'Insufficient Data' }
  }
}

function RentBar({
  label,
  value,
  maxValue,
  color,
}: {
  label: string
  value: number
  maxValue: number
  color: string
}) {
  const pct = maxValue > 0 ? Math.min((value / maxValue) * 100, 100) : 0
  return (
    <div style={{ marginBottom: 8 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 13,
          marginBottom: 2,
        }}
      >
        <span>{label}</span>
        <span style={{ fontWeight: 600 }}>{formatYen(value)}</span>
      </div>
      <div
        style={{
          height: 20,
          background: '#e5e7eb',
          borderRadius: 4,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: color,
            borderRadius: 4,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  )
}

export default function RentComps({ propertyId }: RentCompsProps) {
  const [data, setData] = useState<RentValidationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await api.rentComps.get(propertyId)
      setData(result)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load rent comps')
    } finally {
      setLoading(false)
    }
  }, [propertyId])

  useEffect(() => {
    void load()
  }, [load])

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await api.rentComps.refresh(propertyId)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh comps')
    } finally {
      setRefreshing(false)
    }
  }

  if (loading) {
    return <div style={{ padding: 16, color: '#6b7280' }}>Loading rent comps...</div>
  }

  if (error) {
    return (
      <div style={{ padding: 16 }}>
        <div style={{ color: '#dc2626', marginBottom: 8 }}>{error}</div>
        <button
          type="button"
          onClick={() => void load()}
          style={{
            padding: '6px 14px',
            borderRadius: 4,
            border: '1px solid #d1d5db',
            background: '#fff',
            cursor: 'pointer',
          }}
        >
          Retry
        </button>
      </div>
    )
  }

  if (!data) return null

  const vs = verdictStyle(data.verdict)
  const barMax = Math.max(data.assumed_rent_yen, data.comp_median_yen) * 1.1

  return (
    <div style={{ padding: 16 }}>
      {/* Verdict badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span
          style={{
            display: 'inline-block',
            padding: '4px 12px',
            borderRadius: 12,
            fontSize: 13,
            fontWeight: 600,
            background: vs.bg,
            color: vs.text,
          }}
        >
          {vs.label}
          {data.verdict === 'above_market' && ` +${Math.abs(data.deviation_pct).toFixed(1)}%`}
          {data.verdict === 'below_market' && ` -${Math.abs(data.deviation_pct).toFixed(1)}%`}
        </span>
        <span style={{ fontSize: 13, color: '#6b7280' }}>
          {data.comp_count} comp{data.comp_count !== 1 ? 's' : ''} found
          {data.verdict !== 'insufficient_data' && ` | P${data.percentile}`}
        </span>
      </div>

      {/* Bar chart comparison */}
      <div
        style={{
          background: '#f9fafb',
          borderRadius: 8,
          padding: 16,
          marginBottom: 16,
        }}
      >
        <h4 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 600 }}>
          Rent Comparison
        </h4>
        <RentBar
          label="Assumed Rent"
          value={data.assumed_rent_yen}
          maxValue={barMax}
          color="#3b82f6"
        />
        <RentBar
          label="Comp Median"
          value={data.comp_median_yen}
          maxValue={barMax}
          color="#10b981"
        />
      </div>

      {/* Comps table */}
      {data.comps.length > 0 && (
        <div style={{ overflowX: 'auto', marginBottom: 16 }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: 13,
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: '2px solid #e5e7eb',
                  textAlign: 'left',
                }}
              >
                <th style={{ padding: '6px 8px' }}>Address</th>
                <th style={{ padding: '6px 8px' }}>Size (m2)</th>
                <th style={{ padding: '6px 8px' }}>Madori</th>
                <th style={{ padding: '6px 8px' }}>Walk (min)</th>
                <th style={{ padding: '6px 8px' }}>Rent</th>
                <th style={{ padding: '6px 8px' }}>Mgmt Fee</th>
                <th style={{ padding: '6px 8px' }}>Built</th>
                <th style={{ padding: '6px 8px' }}>Type</th>
              </tr>
            </thead>
            <tbody>
              {data.comps.map((comp) => (
                <tr
                  key={comp.id}
                  style={{ borderBottom: '1px solid #f3f4f6' }}
                >
                  <td style={{ padding: '6px 8px' }}>
                    {comp.address_hint || '\u2014'}
                  </td>
                  <td style={{ padding: '6px 8px' }}>
                    {comp.menseki_m2 != null ? comp.menseki_m2.toFixed(1) : '\u2014'}
                  </td>
                  <td style={{ padding: '6px 8px' }}>{comp.madori || '\u2014'}</td>
                  <td style={{ padding: '6px 8px' }}>
                    {comp.walk_minutes != null ? comp.walk_minutes : '\u2014'}
                  </td>
                  <td style={{ padding: '6px 8px', fontWeight: 600 }}>
                    {formatYen(comp.monthly_rent_yen)}
                  </td>
                  <td style={{ padding: '6px 8px' }}>
                    {formatYen(comp.management_fee_yen)}
                  </td>
                  <td style={{ padding: '6px 8px' }}>
                    {comp.built_year || '\u2014'}
                  </td>
                  <td style={{ padding: '6px 8px' }}>
                    {comp.construction_type || '\u2014'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Refresh button */}
      <button
        type="button"
        onClick={() => void handleRefresh()}
        disabled={refreshing}
        style={{
          padding: '8px 16px',
          borderRadius: 6,
          border: '1px solid #d1d5db',
          background: refreshing ? '#f3f4f6' : '#fff',
          cursor: refreshing ? 'not-allowed' : 'pointer',
          fontSize: 13,
          fontWeight: 500,
        }}
      >
        {refreshing ? 'Refreshing...' : 'Refresh Comps'}
      </button>
    </div>
  )
}
