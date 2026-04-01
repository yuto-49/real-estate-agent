import { useEffect, useRef, useState, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { api } from '../utils/api'
import type { PropertyVisualization, MapOverlay } from '../utils/types'

const BASEMAP = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

interface PropertySimulationMapProps {
  propertyId: string
  onSimulationSelect: (simId: string, batchId?: string) => void
  onVisualizationLoaded?: (viz: PropertyVisualization) => void
}

export default function PropertySimulationMap({
  propertyId,
  onSimulationSelect,
  onVisualizationLoaded,
}: PropertySimulationMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [visualization, setVisualization] = useState<PropertyVisualization | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load property visualization data
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    api.visualization.getProperty(propertyId)
      .then(viz => {
        if (cancelled) return
        setVisualization(viz)
        onVisualizationLoaded?.(viz)
      })
      .catch(err => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load property data')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [propertyId, onVisualizationLoaded])

  // Initialize map when visualization data is ready
  useEffect(() => {
    if (!mapContainer.current || !visualization) return

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: BASEMAP,
      center: [visualization.longitude, visualization.latitude],
      zoom: 14,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-left')
    mapRef.current = map

    map.on('load', () => {
      addPropertyMarker(map, visualization)
      addOverlayLayers(map, visualization.overlays)
    })

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [visualization])

  // Auto-select latest simulation
  const handlePropertyClick = useCallback(() => {
    if (!visualization) return
    if (visualization.simulation_ids.length > 0) {
      onSimulationSelect(visualization.simulation_ids[0])
    }
  }, [visualization, onSimulationSelect])

  if (loading) {
    return (
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fafc' }}>
        <span style={{ color: '#94a3b8' }}>Loading map...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#fef2f2' }}>
        <span style={{ color: '#ef4444' }}>{error}</span>
      </div>
    )
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />

      {/* Property Info Overlay */}
      {visualization && (
        <div
          style={{
            position: 'absolute',
            top: '12px',
            right: '12px',
            backgroundColor: '#fff',
            borderRadius: '8px',
            padding: '12px 16px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            maxWidth: '280px',
            fontSize: '13px',
            zIndex: 10,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>{visualization.address}</div>
          <div style={{ color: '#64748b' }}>
            ${visualization.asking_price.toLocaleString('en-US')}
            {visualization.property_type && ` - ${visualization.property_type.toUpperCase()}`}
          </div>
          {visualization.simulation_ids.length > 0 && (
            <button
              onClick={handlePropertyClick}
              style={{
                marginTop: '8px',
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: 600,
                color: '#fff',
                backgroundColor: '#3b82f6',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                width: '100%',
              }}
            >
              View Simulation Replay ({visualization.simulation_ids.length})
            </button>
          )}
        </div>
      )}

      {/* Legend */}
      {visualization && visualization.overlays.length > 0 && (
        <div
          style={{
            position: 'absolute',
            bottom: '12px',
            left: '12px',
            backgroundColor: '#fff',
            borderRadius: '8px',
            padding: '10px 14px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            fontSize: '11px',
            zIndex: 10,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '6px', color: '#475569' }}>Map Layers</div>
          {getUniqueLegendEntries(visualization.overlays).map((entry, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '3px' }}>
              <span
                style={{
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  backgroundColor: entry.color,
                  display: 'inline-block',
                  flexShrink: 0,
                }}
              />
              <span style={{ color: '#64748b' }}>{entry.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Helper functions ──

function addPropertyMarker(map: maplibregl.Map, viz: PropertyVisualization) {
  // Primary property marker with pulsing effect
  const el = document.createElement('div')
  el.style.width = '20px'
  el.style.height = '20px'
  el.style.borderRadius = '50%'
  el.style.backgroundColor = '#3b82f6'
  el.style.border = '3px solid #fff'
  el.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.3), 0 2px 6px rgba(0,0,0,0.3)'
  el.style.cursor = 'pointer'

  // Pulsing animation
  const style = document.createElement('style')
  style.textContent = `
    @keyframes viz-pulse {
      0% { box-shadow: 0 0 0 3px rgba(59,130,246,0.3), 0 2px 6px rgba(0,0,0,0.3); }
      50% { box-shadow: 0 0 0 8px rgba(59,130,246,0.15), 0 2px 6px rgba(0,0,0,0.3); }
      100% { box-shadow: 0 0 0 3px rgba(59,130,246,0.3), 0 2px 6px rgba(0,0,0,0.3); }
    }
  `
  document.head.appendChild(style)
  el.style.animation = 'viz-pulse 2s ease-in-out infinite'

  const popup = new maplibregl.Popup({ offset: 15, closeButton: false })
    .setHTML(`
      <div style="font-size:13px">
        <strong>${viz.address}</strong><br/>
        $${viz.asking_price.toLocaleString('en-US')}
      </div>
    `)

  new maplibregl.Marker({ element: el })
    .setLngLat([viz.longitude, viz.latitude])
    .setPopup(popup)
    .addTo(map)

  // Add comparable property markers
  for (const comp of viz.comparable_properties) {
    if (!comp.latitude || !comp.longitude) continue
    const compEl = document.createElement('div')
    compEl.style.width = '10px'
    compEl.style.height = '10px'
    compEl.style.borderRadius = '50%'
    compEl.style.backgroundColor = '#8b5cf6'
    compEl.style.border = '2px solid #fff'
    compEl.style.boxShadow = '0 1px 3px rgba(0,0,0,0.2)'

    const compPopup = new maplibregl.Popup({ offset: 10, closeButton: false })
      .setHTML(`
        <div style="font-size:12px">
          <strong>${comp.address}</strong><br/>
          $${comp.asking_price.toLocaleString('en-US')}
        </div>
      `)

    new maplibregl.Marker({ element: compEl })
      .setLngLat([comp.longitude, comp.latitude])
      .setPopup(compPopup)
      .addTo(map)
  }
}

function addOverlayLayers(
  map: maplibregl.Map,
  overlays: MapOverlay[],
) {
  // Group overlays by type for layer creation
  const circleOverlays = overlays.filter(o =>
    o.radius_meters > 0 && (o.overlay_type === 'sentiment_zone' || o.overlay_type === 'risk_zone' || o.overlay_type === 'household_cluster')
  )

  if (circleOverlays.length === 0) return

  // Convert each circle overlay to a GeoJSON polygon (approximate circle with 32 points)
  const features = circleOverlays.map((overlay, idx) => {
    const points = generateCirclePolygon(overlay.center_lat, overlay.center_lng, overlay.radius_meters)
    return {
      type: 'Feature' as const,
      properties: {
        id: `viz-overlay-${idx}`,
        overlay_type: overlay.overlay_type,
        color: overlay.color || '#3b82f6',
        label: overlay.label,
        value: overlay.value,
      },
      geometry: {
        type: 'Polygon' as const,
        coordinates: [points],
      },
    }
  })

  map.addSource('viz-overlays', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features },
  })

  map.addLayer({
    id: 'viz-overlay-fill',
    type: 'fill',
    source: 'viz-overlays',
    paint: {
      'fill-color': ['get', 'color'],
      'fill-opacity': 0.12,
    },
  })

  map.addLayer({
    id: 'viz-overlay-line',
    type: 'line',
    source: 'viz-overlays',
    paint: {
      'line-color': ['get', 'color'],
      'line-width': 1.5,
      'line-dasharray': [4, 3],
      'line-opacity': 0.6,
    },
  })
}

function generateCirclePolygon(lat: number, lng: number, radiusMeters: number, points = 32): [number, number][] {
  const coords: [number, number][] = []
  const earthRadius = 6371000
  for (let i = 0; i <= points; i++) {
    const angle = (i / points) * 2 * Math.PI
    const dLat = (radiusMeters / earthRadius) * Math.cos(angle) * (180 / Math.PI)
    const dLng = (radiusMeters / (earthRadius * Math.cos(lat * Math.PI / 180))) * Math.sin(angle) * (180 / Math.PI)
    coords.push([lng + dLng, lat + dLat])
  }
  return coords
}

function getUniqueLegendEntries(overlays: MapOverlay[]): Array<{ color: string; label: string }> {
  const TYPE_LABELS: Record<string, string> = {
    sentiment_zone: 'Neighborhood Sentiment',
    risk_zone: 'Risk Zone',
    household_cluster: 'Household Cluster',
    comparable: 'Comparable Property',
  }
  const seen = new Set<string>()
  const entries: Array<{ color: string; label: string }> = []

  // Always show primary property
  entries.push({ color: '#3b82f6', label: 'Selected Property' })

  for (const o of overlays) {
    if (seen.has(o.overlay_type)) continue
    seen.add(o.overlay_type)
    entries.push({
      color: o.color || '#3b82f6',
      label: TYPE_LABELS[o.overlay_type] || o.overlay_type,
    })
  }
  return entries
}
