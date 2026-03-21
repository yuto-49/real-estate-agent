import { useState, useEffect, useRef, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { api } from '../utils/api'
import type { UserProfile } from '../utils/types'

interface Props {
  /** Pass an existing user to edit, or null to create a new one */
  user: UserProfile | null
  onClose: () => void
  onSaved: (user: UserProfile) => void
}

const LIFE_STAGES = ['first_time', 'relocating', 'investor', 'downsizing', 'upgrading']
const RISK_LEVELS = ['low', 'moderate', 'high']
const PROPERTY_TYPES = ['sfr', 'condo', 'multifamily', 'townhouse', 'land']
const ROLES = ['buyer', 'seller', 'both']

export default function UserFormModal({ user, onClose, onSaved }: Props) {
  const isEdit = !!user

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('buyer')
  const [budgetMin, setBudgetMin] = useState('')
  const [budgetMax, setBudgetMax] = useState('')
  const [lifeStage, setLifeStage] = useState('')
  const [riskTolerance, setRiskTolerance] = useState('moderate')
  const [timelineDays, setTimelineDays] = useState('90')
  const [zipCode, setZipCode] = useState('')
  const [searchRadius, setSearchRadius] = useState('10')
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const [preferredTypes, setPreferredTypes] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Location picker state
  const [locationQuery, setLocationQuery] = useState('')
  const [suggestions, setSuggestions] = useState<Array<{ display_name: string; lat: string; lon: string }>>([])
  const [searching, setSearching] = useState(false)
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const miniMapRef = useRef<HTMLDivElement>(null)
  const miniMapInstance = useRef<maplibregl.Map | null>(null)
  const markerRef = useRef<maplibregl.Marker | null>(null)
  const miniMapLoaded = useRef(false)

  useEffect(() => {
    if (user) {
      setName(user.name)
      setEmail(user.email)
      setRole(user.role)
      setBudgetMin(user.budget_min != null ? String(user.budget_min) : '')
      setBudgetMax(user.budget_max != null ? String(user.budget_max) : '')
      setLifeStage(user.life_stage ?? '')
      setRiskTolerance(user.risk_tolerance ?? 'moderate')
      setTimelineDays(user.timeline_days != null ? String(user.timeline_days) : '90')
      setZipCode(user.zip_code ?? '')
      setSearchRadius(user.search_radius != null ? String(user.search_radius) : '10')
      setLatitude(user.latitude != null ? String(user.latitude) : '')
      setLongitude(user.longitude != null ? String(user.longitude) : '')
      setPreferredTypes(user.preferred_types ?? [])
    }
  }, [user])

  // Place marker on the mini map
  const placeMarker = useCallback((lat: number, lng: number) => {
    const map = miniMapInstance.current
    if (!map) return
    markerRef.current?.remove()
    markerRef.current = new maplibregl.Marker({ color: '#1a1a2e', draggable: true })
      .setLngLat([lng, lat])
      .addTo(map)
    markerRef.current.on('dragend', () => {
      const lngLat = markerRef.current!.getLngLat()
      setLatitude(String(lngLat.lat))
      setLongitude(String(lngLat.lng))
    })
    map.flyTo({ center: [lng, lat], zoom: 14 })
  }, [])

  // Init mini map
  useEffect(() => {
    if (!miniMapRef.current || miniMapInstance.current) return
    const map = new maplibregl.Map({
      container: miniMapRef.current,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: [longitude ? Number(longitude) : -87.6298, latitude ? Number(latitude) : 41.8781],
      zoom: latitude ? 12 : 3,
    })
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.on('load', () => { miniMapLoaded.current = true })

    // Click to place marker
    map.on('click', (e) => {
      const { lat, lng } = e.lngLat
      setLatitude(String(lat))
      setLongitude(String(lng))
      placeMarker(lat, lng)
    })

    miniMapInstance.current = map

    // If editing and has coordinates, place marker
    if (latitude && longitude) {
      map.on('load', () => {
        placeMarker(Number(latitude), Number(longitude))
      })
    }

    return () => {
      map.remove()
      miniMapInstance.current = null
      miniMapLoaded.current = false
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Geocode search with debounce
  const handleLocationSearch = (query: string) => {
    setLocationQuery(query)
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    if (query.trim().length < 3) {
      setSuggestions([])
      return
    }
    searchTimeout.current = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(query)}`,
          { headers: { 'Accept': 'application/json' } }
        )
        const data = await res.json() as Array<{ display_name: string; lat: string; lon: string }>
        setSuggestions(data)
      } catch {
        setSuggestions([])
      } finally {
        setSearching(false)
      }
    }, 400)
  }

  const selectSuggestion = (s: { display_name: string; lat: string; lon: string }) => {
    setLatitude(s.lat)
    setLongitude(s.lon)
    setLocationQuery(s.display_name)
    setSuggestions([])
    placeMarker(Number(s.lat), Number(s.lon))
  }

  const toggleType = (t: string) => {
    setPreferredTypes((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!name.trim() || !email.trim()) {
      setError('Name and email are required.')
      return
    }

    const payload: Record<string, unknown> = {
      name: name.trim(),
      email: email.trim(),
      role,
      budget_min: budgetMin ? Number(budgetMin) : null,
      budget_max: budgetMax ? Number(budgetMax) : null,
      life_stage: lifeStage || null,
      risk_tolerance: riskTolerance,
      timeline_days: timelineDays ? Number(timelineDays) : 90,
      zip_code: zipCode || null,
      search_radius: searchRadius ? Number(searchRadius) : 10,
      latitude: latitude ? Number(latitude) : null,
      longitude: longitude ? Number(longitude) : null,
      preferred_types: preferredTypes,
      investment_goals: {},
    }

    setSaving(true)
    try {
      let result: UserProfile
      if (isEdit) {
        // Don't send email on update (can't change)
        const { email: _email, ...updatePayload } = payload
        result = (await api.users.update(user!.id, updatePayload)) as unknown as UserProfile
      } else {
        result = (await api.users.create(payload as Parameters<typeof api.users.create>[0])) as unknown as UserProfile
      }
      onSaved(result)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save'
      setError(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content user-form-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{isEdit ? 'Edit Profile' : 'Create Account'}</h3>
          <button className="modal-close-btn" onClick={onClose}>&times;</button>
        </div>

        <form onSubmit={handleSubmit} className="user-form">
          {error && <div className="form-error">{error}</div>}

          {/* Identity section */}
          <div className="form-section">
            <h4>Identity</h4>
            <div className="form-row">
              <div className="form-group">
                <label>Full Name *</label>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" required />
              </div>
              <div className="form-group">
                <label>Email *</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="jane@example.com" required disabled={isEdit} />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Role</label>
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Life Stage</label>
                <select value={lifeStage} onChange={(e) => setLifeStage(e.target.value)}>
                  <option value="">— Select —</option>
                  {LIFE_STAGES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                </select>
              </div>
            </div>
          </div>

          {/* Budget section */}
          <div className="form-section">
            <h4>Budget & Strategy</h4>
            <div className="form-row">
              <div className="form-group">
                <label>Min Budget ($)</label>
                <input type="number" value={budgetMin} onChange={(e) => setBudgetMin(e.target.value)} placeholder="150000" />
              </div>
              <div className="form-group">
                <label>Max Budget ($)</label>
                <input type="number" value={budgetMax} onChange={(e) => setBudgetMax(e.target.value)} placeholder="500000" />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Risk Tolerance</label>
                <select value={riskTolerance} onChange={(e) => setRiskTolerance(e.target.value)}>
                  {RISK_LEVELS.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Timeline (days)</label>
                <input type="number" value={timelineDays} onChange={(e) => setTimelineDays(e.target.value)} placeholder="90" />
              </div>
            </div>
          </div>

          {/* Location section */}
          <div className="form-section">
            <h4>Location</h4>

            {/* Address search */}
            <div className="form-group" style={{ position: 'relative', marginBottom: '0.6rem' }}>
              <label>Search Address</label>
              <input
                value={locationQuery}
                onChange={(e) => handleLocationSearch(e.target.value)}
                placeholder="Type an address, city, or place..."
              />
              {searching && <span className="location-searching">Searching...</span>}
              {suggestions.length > 0 && (
                <ul className="location-suggestions">
                  {suggestions.map((s, i) => (
                    <li key={i} onClick={() => selectSuggestion(s)}>{s.display_name}</li>
                  ))}
                </ul>
              )}
            </div>

            {/* Mini map — click or drag to set location */}
            <div className="location-map-wrapper">
              <div ref={miniMapRef} className="location-mini-map" />
              <span className="location-map-hint">Click the map or drag the pin to set location</span>
            </div>

            {/* Coordinates (read-only) + zip/radius */}
            <div className="form-row" style={{ marginTop: '0.6rem' }}>
              <div className="form-group">
                <label>Latitude</label>
                <input value={latitude} readOnly placeholder="—" />
              </div>
              <div className="form-group">
                <label>Longitude</label>
                <input value={longitude} readOnly placeholder="—" />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>ZIP Code</label>
                <input value={zipCode} onChange={(e) => setZipCode(e.target.value)} placeholder="60614" />
              </div>
              <div className="form-group">
                <label>Search Radius (mi)</label>
                <input type="number" value={searchRadius} onChange={(e) => setSearchRadius(e.target.value)} placeholder="10" />
              </div>
            </div>
          </div>

          {/* Preferred types */}
          <div className="form-section">
            <h4>Preferred Property Types</h4>
            <div className="form-chip-group">
              {PROPERTY_TYPES.map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`form-chip ${preferredTypes.includes(t) ? 'active' : ''}`}
                  onClick={() => toggleType(t)}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="form-actions">
            <button type="button" className="secondary-btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary-btn" disabled={saving}>
              {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
