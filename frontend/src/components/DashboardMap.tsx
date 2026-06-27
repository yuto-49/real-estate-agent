import { useEffect, useRef, useState, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Property, UserProfile } from '../utils/types'

type MapMode = 'properties' | 'heatmap' | 'buyer-ability'

interface Props {
  properties: Property[]
  selectedUser: UserProfile | null
  onPropertyClick?: (property: Property) => void
}

const BASEMAP = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
const SOURCE_ID = 'properties'

function toGeoJSON(properties: Property[]): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: properties
      .filter((p) => p.latitude && p.longitude)
      .map((p) => ({
        type: 'Feature' as const,
        geometry: { type: 'Point' as const, coordinates: [p.longitude!, p.latitude!] },
        properties: {
          id: p.id,
          address: p.address,
          asking_price: p.asking_price,
          bedrooms: p.bedrooms ?? null,
          bathrooms: p.bathrooms ?? null,
          property_type: p.property_type ?? '',
        },
      })),
  }
}

function removeLayers(map: maplibregl.Map) {
  const layerIds = (map.getStyle()?.layers ?? [])
    .filter((l) => l.id.startsWith('props-'))
    .map((l) => l.id)
  layerIds.forEach((id) => {
    if (map.getLayer(id)) map.removeLayer(id)
  })
  if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID)
}

export default function DashboardMap({ properties, selectedUser, onPropertyClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const mapLoaded = useRef(false)
  const popupRef = useRef<maplibregl.Popup | null>(null)
  const [mode, setMode] = useState<MapMode>('properties')

  // Init map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASEMAP,
      center: [-87.6298, 41.8781],
      zoom: 10,
    })
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.on('load', () => { mapLoaded.current = true })
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
      mapLoaded.current = false
    }
  }, [])

  // Fly to user location
  useEffect(() => {
    const map = mapRef.current
    if (!map || !selectedUser?.latitude || !selectedUser?.longitude) return
    map.flyTo({ center: [selectedUser.longitude, selectedUser.latitude], zoom: 12 })
  }, [selectedUser])

  // Click handler for property modes
  const handleClick = useCallback(
    (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
      const map = mapRef.current
      if (!map || !e.features?.length) return
      const f = e.features[0]
      const coords = (f.geometry as GeoJSON.Point).coordinates.slice() as [number, number]
      const props = f.properties

      popupRef.current?.remove()

      const price = Number(props.asking_price)
      let html = `<strong>$${price.toLocaleString()}</strong><br/>${props.address}<br/>${props.bedrooms ?? '?'} bed / ${props.bathrooms ?? '?'} bath`

      if (mode === 'buyer-ability' && selectedUser?.budget_max) {
        const budget = selectedUser.budget_max
        const label = price <= budget ? 'Within Budget' : price <= budget * 1.15 ? 'Stretch' : 'Over Budget'
        html += `<br/><em>${label}</em>`
      }

      popupRef.current = new maplibregl.Popup({ offset: 12 }).setLngLat(coords).setHTML(html).addTo(map)

      if (onPropertyClick) {
        const prop = properties.find((p) => p.id === props.id)
        if (prop) onPropertyClick(prop)
      }
    },
    [mode, selectedUser, properties, onPropertyClick],
  )

  // Mode switching — add layers
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const apply = () => {
      removeLayers(map)
      popupRef.current?.remove()

      const geojson = toGeoJSON(properties)
      if (geojson.features.length === 0) return

      if (mode === 'properties') {
        map.addSource(SOURCE_ID, {
          type: 'geojson',
          data: geojson,
          cluster: true,
          clusterMaxZoom: 14,
          clusterRadius: 50,
        })

        map.addLayer({
          id: 'props-clusters',
          type: 'circle',
          source: SOURCE_ID,
          filter: ['has', 'point_count'],
          paint: {
            'circle-color': '#1a1a2e',
            'circle-radius': ['step', ['get', 'point_count'], 18, 10, 24, 50, 32],
            'circle-opacity': 0.85,
          },
        })

        map.addLayer({
          id: 'props-cluster-count',
          type: 'symbol',
          source: SOURCE_ID,
          filter: ['has', 'point_count'],
          layout: { 'text-field': '{point_count_abbreviated}', 'text-size': 13 },
          paint: { 'text-color': '#ffffff' },
        })

        map.addLayer({
          id: 'props-points',
          type: 'circle',
          source: SOURCE_ID,
          filter: ['!', ['has', 'point_count']],
          paint: {
            'circle-color': '#1a1a2e',
            'circle-radius': 8,
            'circle-stroke-width': 2,
            'circle-stroke-color': '#ffffff',
          },
        })

        map.on('click', 'props-points', handleClick as unknown as (e: maplibregl.MapMouseEvent) => void)
        map.on('mouseenter', 'props-points', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'props-points', () => { map.getCanvas().style.cursor = '' })

        map.on('click', 'props-clusters', async (e) => {
          const features = map.queryRenderedFeatures(e.point, { layers: ['props-clusters'] })
          if (!features.length) return
          const clusterId = features[0].properties.cluster_id
          try {
            const zoom = await (map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource).getClusterExpansionZoom(clusterId)
            map.easeTo({ center: (features[0].geometry as GeoJSON.Point).coordinates as [number, number], zoom })
          } catch { /* ignore */ }
        })
      } else if (mode === 'heatmap') {
        map.addSource(SOURCE_ID, { type: 'geojson', data: geojson })

        const prices = geojson.features.map((f) => f.properties!.asking_price as number)
        const minPrice = Math.min(...prices)
        const maxPrice = Math.max(...prices)

        map.addLayer({
          id: 'props-heatmap',
          type: 'heatmap',
          source: SOURCE_ID,
          paint: {
            'heatmap-weight': maxPrice > minPrice
              ? ['interpolate', ['linear'], ['get', 'asking_price'], minPrice, 0, maxPrice, 1]
              : 0.5,
            'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 15, 3],
            'heatmap-color': [
              'interpolate', ['linear'], ['heatmap-density'],
              0, 'rgba(33,102,172,0)',
              0.2, 'rgb(103,169,207)',
              0.4, 'rgb(209,229,240)',
              0.6, 'rgb(253,219,199)',
              0.8, 'rgb(239,138,98)',
              1, 'rgb(178,24,43)',
            ],
            'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 2, 15, 20],
            'heatmap-opacity': 0.8,
          },
        })
      } else if (mode === 'buyer-ability') {
        map.addSource(SOURCE_ID, { type: 'geojson', data: geojson })

        const budgetMax = selectedUser?.budget_max
        const circleColor = (budgetMax
          ? [
              'case',
              ['<=', ['get', 'asking_price'], budgetMax], '#22c55e',
              ['<=', ['get', 'asking_price'], budgetMax * 1.15], '#eab308',
              '#ef4444',
            ]
          : '#999999') as maplibregl.ExpressionSpecification

        map.addLayer({
          id: 'props-budget',
          type: 'circle',
          source: SOURCE_ID,
          paint: {
            'circle-color': circleColor,
            'circle-radius': 10,
            'circle-stroke-width': 2,
            'circle-stroke-color': '#ffffff',
          },
        })

        map.on('click', 'props-budget', handleClick as unknown as (e: maplibregl.MapMouseEvent) => void)
        map.on('mouseenter', 'props-budget', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'props-budget', () => { map.getCanvas().style.cursor = '' })
      }

      // Fit bounds
      const coords = geojson.features.map((f) => (f.geometry as GeoJSON.Point).coordinates as [number, number])
      if (coords.length > 0) {
        const bounds = new maplibregl.LngLatBounds(coords[0], coords[0])
        coords.forEach((c) => bounds.extend(c))
        map.fitBounds(bounds, { padding: 60, maxZoom: 14 })
      }
    }

    if (mapLoaded.current) {
      apply()
    } else {
      mapRef.current?.on('load', apply)
    }
  }, [mode, properties, selectedUser, handleClick])

  return (
    <div className="dashboard-map-area">
      {/* Mode toggle */}
      <div className="map-mode-toggle">
        {(['properties', 'heatmap', 'buyer-ability'] as MapMode[]).map((m) => (
          <button
            key={m}
            className={mode === m ? 'active' : ''}
            onClick={() => setMode(m)}
          >
            {m === 'properties' ? 'Properties' : m === 'heatmap' ? 'Heatmap' : 'Budget'}
          </button>
        ))}
      </div>

      {/* Buyer ability overlay when no user selected */}
      {mode === 'buyer-ability' && !selectedUser?.budget_max && (
        <div className="map-overlay-message">Select a buyer to see purchase ability</div>
      )}

      {/* Budget legend */}
      {mode === 'buyer-ability' && selectedUser?.budget_max && (
        <div className="map-legend">
          <div className="map-legend-title">Budget: ${selectedUser.budget_max.toLocaleString()}</div>
          <div className="map-legend-item"><span className="map-legend-dot map-legend-dot--success" />Within Budget</div>
          <div className="map-legend-item"><span className="map-legend-dot map-legend-dot--budget" />Stretch (up to +15%)</div>
          <div className="map-legend-item"><span className="map-legend-dot map-legend-dot--danger" />Over Budget</div>
        </div>
      )}

      <div ref={containerRef} className="dashboard-map-canvas" />
    </div>
  )
}
