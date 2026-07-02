import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PropertyCard from './PropertyCard'
import MapView from './MapView'
import type { Property } from '../utils/types'
import { api } from '../utils/api'

const LOCATIONS = [
  { label: '東京23区', zip: '1000001', lat: 35.6762, lng: 139.6503 },
  { label: '千代田区 (100-0001)', zip: '1000001', lat: 35.6938, lng: 139.7532 },
  { label: '新宿区 (160-0023)', zip: '1600023', lat: 35.6938, lng: 139.7036 },
  { label: '渋谷区 (150-0001)', zip: '1500001', lat: 35.6619, lng: 139.7041 },
  { label: '板橋区 (173-0004)', zip: '1730004', lat: 35.7516, lng: 139.7094 },
  { label: '練馬区 (176-0001)', zip: '1760001', lat: 35.7356, lng: 139.6517 },
  { label: '杉並区 (166-0001)', zip: '1660001', lat: 35.6994, lng: 139.6364 },
  { label: '江戸川区 (132-0001)', zip: '1320001', lat: 35.7068, lng: 139.8685 },
]

interface Props {
  open: boolean
  onClose: () => void
}

export default function SearchDrawer({ open, onClose }: Props) {
  const navigate = useNavigate()
  const [properties, setProperties] = useState<Property[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null)
  const [filters, setFilters] = useState({
    minPrice: '',
    maxPrice: '',
    propertyType: '',
    locationIdx: 0,
  })

  useEffect(() => {
    if (open) void loadProperties()
  }, [open])

  const loadProperties = async () => {
    setLoading(true)
    setError('')
    try {
      const params: Record<string, string> = {}
      if (filters.minPrice) params.min_price = filters.minPrice
      if (filters.maxPrice) params.max_price = filters.maxPrice
      if (filters.propertyType) params.property_type = filters.propertyType
      const data = await api.properties.list(params)
      setProperties(data.properties as Property[])
    } catch (err) {
      setProperties([])
      setError(err instanceof Error ? err.message : 'Failed to load properties')
    } finally {
      setLoading(false)
    }
  }

  if (!open) return null

  const selectedLocation = LOCATIONS[filters.locationIdx]

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel drawer-right" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <h3>Property Search</h3>
          <button className="drawer-close-btn" onClick={onClose}>x</button>
        </div>

        <div className="drawer-body">
          <p style={{ color: '#666', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
            Map Focus changes the map center only. Property filtering below uses price/type fields.
          </p>
          <div className="search-filters" style={{ marginBottom: '1rem' }}>
            <select
              value={filters.locationIdx}
              onChange={(e) => setFilters((f) => ({ ...f, locationIdx: Number(e.target.value) }))}
            >
              {LOCATIONS.map((loc, idx) => (
                <option key={loc.zip + idx} value={idx}>{loc.label}</option>
              ))}
            </select>
            <input type="number" placeholder="Min Price" value={filters.minPrice} onChange={(e) => setFilters((f) => ({ ...f, minPrice: e.target.value }))} />
            <input type="number" placeholder="Max Price" value={filters.maxPrice} onChange={(e) => setFilters((f) => ({ ...f, maxPrice: e.target.value }))} />
            <select value={filters.propertyType} onChange={(e) => setFilters((f) => ({ ...f, propertyType: e.target.value }))}>
              <option value="">All Types</option>
              <option value="aparuto">アパート</option>
              <option value="mansion">マンション</option>
              <option value="ikkodate">一戸建て</option>
              <option value="one_room">ワンルーム</option>
            </select>
            <button onClick={() => void loadProperties()} disabled={loading}>
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>

          {error && (
            <div style={{ marginBottom: '0.75rem' }}>
              <p className="error" style={{ marginBottom: '0.4rem' }}>{error}</p>
              <button className="secondary-btn" onClick={() => void loadProperties()} disabled={loading}>
                Retry
              </button>
            </div>
          )}

          <div className="map-container" style={{ height: '250px', marginBottom: '1rem' }}>
            <MapView
              properties={properties}
              center={{ lat: selectedLocation.lat, lng: selectedLocation.lng }}
              onMarkerClick={setSelectedProperty}
            />
          </div>

          <div className="property-list" style={{ maxHeight: '400px' }}>
            {loading ? (
              <p>Loading...</p>
            ) : properties.length === 0 ? (
              <p>No properties found.</p>
            ) : (
              properties.map((p) => (
                <PropertyCard key={p.id} property={p} onSelect={setSelectedProperty} />
              ))
            )}
          </div>
        </div>

        {selectedProperty && (
          <div className="drawer-footer">
            <p style={{ fontWeight: 600 }}>{selectedProperty.address} — ¥{selectedProperty.asking_price?.toLocaleString()}</p>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
              <button
                className="primary-btn"
                onClick={() => {
                  const params = new URLSearchParams({
                    property_id: selectedProperty.id,
                    address: selectedProperty.address,
                    price: String(selectedProperty.asking_price ?? ''),
                  })
                  navigate(`/negotiate?${params.toString()}`)
                  onClose()
                }}
              >
                Negotiate
              </button>
              <button className="secondary-btn" onClick={() => setSelectedProperty(null)}>Clear</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
