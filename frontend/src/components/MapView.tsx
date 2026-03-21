import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Property } from '../utils/types'

interface MapViewProps {
  properties: Property[]
  center?: { lat: number; lng: number }
  zoom?: number
  onMarkerClick?: (property: Property) => void
}

// Uses OpenStreetMap tiles by default (free, no API key needed).
// To use TomTom vector tiles, set:
//   style: `https://api.tomtom.com/style/2/custom/style/dG9tdG9t.........json?key=${TOMTOM_API_KEY}`
const DEFAULT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

export default function MapView({
  properties,
  center = { lat: 41.8781, lng: -87.6298 },
  zoom = 12,
  onMarkerClick,
}: MapViewProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])

  // Initialize map once
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return

    mapInstanceRef.current = new maplibregl.Map({
      container: mapRef.current,
      style: DEFAULT_STYLE,
      center: [center.lng, center.lat],
      zoom,
    })

    mapInstanceRef.current.addControl(new maplibregl.NavigationControl(), 'top-right')

    return () => {
      mapInstanceRef.current?.remove()
      mapInstanceRef.current = null
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Keep map center in sync with caller-selected location.
  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map) return
    map.easeTo({ center: [center.lng, center.lat], duration: 500 })
  }, [center.lat, center.lng])

  // Update markers when properties change
  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map) return

    // Clear existing markers
    markersRef.current.forEach((m) => m.remove())
    markersRef.current = []

    // Add property markers
    const newMarkers = properties
      .filter((p) => p.latitude && p.longitude)
      .map((property) => {
        const popup = new maplibregl.Popup({ offset: 25 }).setHTML(
          `<strong>$${property.asking_price?.toLocaleString()}</strong>
           <br/>${property.address}
           <br/>${property.bedrooms ?? '?'} bed / ${property.bathrooms ?? '?'} bath`
        )

        const marker = new maplibregl.Marker({ color: '#1a1a2e' })
          .setLngLat([property.longitude!, property.latitude!])
          .setPopup(popup)
          .addTo(map)

        marker.getElement().addEventListener('click', () => {
          onMarkerClick?.(property)
        })

        return marker
      })

    markersRef.current = newMarkers

    // Fit bounds if we have properties
    if (newMarkers.length > 1) {
      const bounds = new maplibregl.LngLatBounds()
      newMarkers.forEach((m) => bounds.extend(m.getLngLat()))
      map.fitBounds(bounds, { padding: 50 })
    }
  }, [properties, onMarkerClick])

  return <div ref={mapRef} className="map-view" style={{ width: '100%', height: '500px' }} />
}
