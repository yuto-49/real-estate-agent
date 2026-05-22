import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

import type { PropertyTickState } from '../utils/types'

const BASEMAP = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

interface MarketSimulationMapProps {
  states: PropertyTickState[]
  selectedPropertyId: string | null
  onSelectProperty: (propertyId: string) => void
}

interface MarkerRecord {
  element: HTMLDivElement
  marker: maplibregl.Marker
}

export default function MarketSimulationMap({
  states,
  selectedPropertyId,
  onSelectProperty,
}: MarketSimulationMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<Record<string, MarkerRecord>>({})

  useEffect(() => {
    if (!mapContainerRef.current || states.length === 0 || mapRef.current) return

    const geocoded = states.filter((state) => state.latitude != null && state.longitude != null)
    const center: [number, number] = geocoded.length > 0
      ? [
          geocoded.reduce((sum, state) => sum + Number(state.longitude || 0), 0) / geocoded.length,
          geocoded.reduce((sum, state) => sum + Number(state.latitude || 0), 0) / geocoded.length,
        ]
      : [-87.6298, 41.8781]

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: BASEMAP,
      center,
      zoom: geocoded.length > 1 ? 11.75 : 12.5,
    })
    map.addControl(new maplibregl.NavigationControl(), 'top-left')
    mapRef.current = map

    return () => {
      Object.values(markersRef.current).forEach(({ marker }) => marker.remove())
      markersRef.current = {}
      map.remove()
      mapRef.current = null
    }
  }, [states])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const nextIds = new Set(states.map((state) => state.property_id))
    for (const [propertyId, record] of Object.entries(markersRef.current)) {
      if (!nextIds.has(propertyId)) {
        record.marker.remove()
        delete markersRef.current[propertyId]
      }
    }

    for (const state of states) {
      if (state.latitude == null || state.longitude == null) continue
      let record = markersRef.current[state.property_id]
      if (!record) {
        const element = document.createElement('div')
        element.className = 'market-map-marker'
        element.addEventListener('click', () => onSelectProperty(state.property_id))
        const marker = new maplibregl.Marker({ element })
          .setLngLat([Number(state.longitude), Number(state.latitude)])
          .addTo(map)
        record = { element, marker }
        markersRef.current[state.property_id] = record
      }
      record.marker.setLngLat([Number(state.longitude), Number(state.latitude)])
      styleMarker(record.element, state, selectedPropertyId === state.property_id)
      const bidLabel = state.top_bid != null
        ? 'Top bid $' + Math.round(state.top_bid).toLocaleString()
        : 'No bids yet'
      record.element.title = [
        state.address,
        'Attention ' + String(state.attention_count),
        bidLabel,
      ].join(' | ')
    }
  }, [onSelectProperty, selectedPropertyId, states])

  return <div ref={mapContainerRef} className="market-sim-map" />
}

function styleMarker(element: HTMLDivElement, state: PropertyTickState, selected: boolean) {
  const markerSize = Math.max(14, Math.min(30, 14 + state.attention_count * 3 + state.local_competition * 2))
  const markerColor = state.status === 'acquired'
    ? '#0f766e'
    : state.local_competition >= 2
      ? '#d97706'
      : state.attention_count > 0
        ? '#2563eb'
        : '#94a3b8'

  element.style.width = String(markerSize) + 'px'
  element.style.height = String(markerSize) + 'px'
  element.style.borderRadius = '999px'
  element.style.background = markerColor
  element.style.border = selected ? '4px solid #111827' : '3px solid rgba(255,255,255,0.95)'
  element.style.boxShadow = selected
    ? '0 0 0 6px rgba(17,24,39,0.15), 0 10px 24px rgba(15,23,42,0.25)'
    : '0 8px 20px rgba(15,23,42,0.18)'
  element.style.cursor = 'pointer'
  element.style.display = 'grid'
  element.style.placeItems = 'center'
  element.style.color = '#fff'
  element.style.fontSize = '10px'
  element.style.fontWeight = '700'
  element.textContent = state.status === 'acquired' ? '$' : state.attention_count > 0 ? String(state.attention_count) : ''
}
