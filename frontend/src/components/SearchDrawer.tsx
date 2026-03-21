import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PropertyCard from './PropertyCard'
import MapView from './MapView'
import type { Property } from '../utils/types'
import { api } from '../utils/api'

const LOCATIONS = [
  { label: 'All Chicago', zip: '60601', lat: 41.8781, lng: -87.6298 },
  { label: 'The Loop (60601)', zip: '60601', lat: 41.8819, lng: -87.6278 },
  { label: 'Near North (60602)', zip: '60602', lat: 41.8858, lng: -87.6316 },
  { label: 'Lincoln Park (60614)', zip: '60614', lat: 41.9214, lng: -87.6513 },
  { label: 'Wicker Park (60622)', zip: '60622', lat: 41.9088, lng: -87.6796 },
  { label: 'Uptown (60640)', zip: '60640', lat: 41.9654, lng: -87.6564 },
  { label: 'Logan Square (60647)', zip: '60647', lat: 41.9234, lng: -87.7100 },
  { label: 'Lakeview (60657)', zip: '60657', lat: 41.9403, lng: -87.6537 },
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
              <option value="sfr">Single Family</option>
              <option value="condo">Condo</option>
              <option value="duplex">Duplex</option>
              <option value="triplex">Triplex</option>
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
            <p style={{ fontWeight: 600 }}>{selectedProperty.address} — ${selectedProperty.asking_price?.toLocaleString()}</p>
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
