import { useState, useEffect, useRef, useCallback } from 'react'

export interface Property {
  id: string
  address: string
  asking_price: number
  menseki_m2: number | null
  walk_minutes_to_station: number | null
  built_year: number | null
  asset_tier: string | null
  construction_type: string | null
  assumed_monthly_rent_yen: number | null
  ward_code: string | null
  baibai_kakaku_yen: number | null
}

interface PropertyInputProps {
  onPropertySelected: (property: Property) => void
  selectedProperty: Property | null
  onAnalyze: () => void
  analyzing: boolean
}

function formatPrice(property: Property): string {
  const raw = property.baibai_kakaku_yen ?? property.asking_price
  return Math.round(Number(raw) / 10000).toLocaleString() + '万円'
}

export default function PropertyInput({
  onPropertySelected,
  selectedProperty,
  onAnalyze,
  analyzing,
}: PropertyInputProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Property[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [searching, setSearching] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([])
      setShowDropdown(false)
      return
    }
    setSearching(true)
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=10`)
      if (res.ok) {
        const data = await res.json()
        setResults(Array.isArray(data) ? data : (data.results ?? []))
        setShowDropdown(true)
      }
    } catch {
      // silently ignore search errors
    } finally {
      setSearching(false)
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => search(query), 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, search])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function handleSelect(property: Property) {
    onPropertySelected(property)
    setQuery('')
    setResults([])
    setShowDropdown(false)
  }

  function handleClear() {
    onPropertySelected(null as unknown as Property)
    setQuery('')
    setResults([])
    setShowDropdown(false)
  }

  return (
    <div>
      <div className="ws-card">
        <h3>Property Search</h3>
        <div className="ws-search-wrapper" ref={wrapperRef}>
          <input
            className="ws-search-input"
            type="text"
            placeholder="Search by address or area..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => results.length > 0 && setShowDropdown(true)}
            disabled={!!selectedProperty}
          />
          {showDropdown && results.length > 0 && (
            <ul className="ws-search-results">
              {results.map((p) => (
                <li key={p.id} onMouseDown={() => handleSelect(p)}>
                  <div className="ws-search-result-address">{p.address}</div>
                  <div className="ws-search-result-meta">
                    {formatPrice(p)}
                    {p.menseki_m2 != null && ` · ${p.menseki_m2}m²`}
                    {p.asset_tier && ` · ${p.asset_tier}`}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {searching && (
            <div style={{ fontSize: 11, color: '#aaa', marginTop: 4 }}>Searching...</div>
          )}
        </div>
      </div>

      {selectedProperty ? (
        <div className="ws-card">
          <h3>Selected Property</h3>
          <div className="ws-property-stat">
            <span className="ws-property-stat-label">Address</span>
            <span className="ws-property-stat-value" style={{ maxWidth: 160, textAlign: 'right', fontSize: 12 }}>
              {selectedProperty.address}
            </span>
          </div>
          <div className="ws-property-stat">
            <span className="ws-property-stat-label">Price</span>
            <span className="ws-property-stat-value">{formatPrice(selectedProperty)}</span>
          </div>
          {selectedProperty.menseki_m2 != null && (
            <div className="ws-property-stat">
              <span className="ws-property-stat-label">Size</span>
              <span className="ws-property-stat-value">{selectedProperty.menseki_m2} m²</span>
            </div>
          )}
          {selectedProperty.walk_minutes_to_station != null && (
            <div className="ws-property-stat">
              <span className="ws-property-stat-label">Walk to Station</span>
              <span className="ws-property-stat-value">{selectedProperty.walk_minutes_to_station} min</span>
            </div>
          )}
          {selectedProperty.built_year != null && (
            <div className="ws-property-stat">
              <span className="ws-property-stat-label">Built Year</span>
              <span className="ws-property-stat-value">{selectedProperty.built_year}</span>
            </div>
          )}
          {selectedProperty.asset_tier && (
            <div className="ws-property-stat">
              <span className="ws-property-stat-label">Asset Tier</span>
              <span className="ws-property-stat-value">{selectedProperty.asset_tier}</span>
            </div>
          )}
          {selectedProperty.construction_type && (
            <div className="ws-property-stat">
              <span className="ws-property-stat-label">Construction</span>
              <span className="ws-property-stat-value">{selectedProperty.construction_type}</span>
            </div>
          )}
          {selectedProperty.assumed_monthly_rent_yen != null && (
            <div className="ws-property-stat">
              <span className="ws-property-stat-label">Assumed Rent</span>
              <span className="ws-property-stat-value">
                {Math.round(selectedProperty.assumed_monthly_rent_yen).toLocaleString()}円/月
              </span>
            </div>
          )}

          <button className="ws-btn-primary" onClick={onAnalyze} disabled={analyzing}>
            {analyzing ? 'Analyzing...' : 'Analyze This Property'}
          </button>
          <button className="ws-btn-secondary" onClick={handleClear}>
            Clear Selection
          </button>
        </div>
      ) : (
        <div className="ws-empty">
          <span className="ws-empty-icon">🏠</span>
          <span className="ws-empty-text">Search for a property above to get started</span>
        </div>
      )}
    </div>
  )
}
