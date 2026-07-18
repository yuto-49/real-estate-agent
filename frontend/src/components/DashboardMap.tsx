import { useEffect, useRef, useState, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { formatAssetClassLabel, formatJpyCompact } from '../utils/japan'
import { hasValidCoordinates } from '../utils/map'
import type { PortfolioHolding, Property, UserProfile } from '../utils/types'

type MapMode = 'properties' | 'heatmap' | 'buyer-ability'

interface Props {
  properties: Property[]
  holdings: PortfolioHolding[]
  selectedUser: UserProfile | null
  onPropertyClick?: (property: Property) => void
}

const BASEMAP = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
const MARKET_SOURCE_ID = 'properties'
const HOLDING_SOURCE_ID = 'holdings'

function toPropertyGeoJSON(properties: Property[]): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: properties
      .filter((p) => hasValidCoordinates(p.latitude, p.longitude))
      .map((p) => ({
        type: 'Feature' as const,
        geometry: { type: 'Point' as const, coordinates: [p.longitude!, p.latitude!] },
        properties: {
          id: p.id,
          source: 'market',
          address: p.address,
          asking_price: p.asking_price,
          bedrooms: p.bedrooms ?? null,
          bathrooms: p.bathrooms ?? null,
          property_type: p.property_type ?? '',
        },
      })),
  }
}

function toHoldingGeoJSON(holdings: PortfolioHolding[]): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: holdings
      .filter((holding) => hasValidCoordinates(holding.latitude, holding.longitude))
      .map((holding) => ({
        type: 'Feature' as const,
        geometry: {
          type: 'Point' as const,
          coordinates: [holding.longitude!, holding.latitude!],
        },
        properties: {
          id: holding.id,
          source: 'holding',
          address: holding.address,
          asset_class: holding.asset_class,
          status: holding.status,
          zip_code: holding.zip_code ?? '',
          monthly_rent: holding.financials?.monthly_rent ?? null,
        },
      })),
  }
}

function removeLayers(map: maplibregl.Map) {
  const layerIds = (map.getStyle()?.layers ?? [])
    .filter((l) => l.id.startsWith('props-') || l.id.startsWith('holdings-'))
    .map((l) => l.id)
  layerIds.forEach((id) => {
    if (map.getLayer(id)) map.removeLayer(id)
  })
  if (map.getSource(MARKET_SOURCE_ID)) map.removeSource(MARKET_SOURCE_ID)
  if (map.getSource(HOLDING_SOURCE_ID)) map.removeSource(HOLDING_SOURCE_ID)
}

export default function DashboardMap({
  properties,
  holdings,
  selectedUser,
  onPropertyClick,
}: Props) {
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
      center: [139.6917, 35.6895],
      zoom: 9,
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

      if (props.source === 'holding') {
        const monthlyRent = Number(props.monthly_rent)
        const rentLabel = Number.isFinite(monthlyRent)
          ? `月額賃料 ${formatJpyCompact(monthlyRent)}`
          : '月額賃料 未設定'
        const zipLabel = props.zip_code ? `〒${props.zip_code}` : '郵便番号未設定'
        const html = [
          `<strong>保有物件</strong>`,
          props.address,
          `${formatAssetClassLabel(String(props.asset_class || ''))} / ${props.status || 'held'}`,
          `${zipLabel} / ${rentLabel}`,
        ].join('<br/>')
        popupRef.current = new maplibregl.Popup({ offset: 12 })
          .setLngLat(coords)
          .setHTML(html)
          .addTo(map)
        return
      }

      const price = Number(props.asking_price)
      let html = `<strong>${formatJpyCompact(price)}</strong><br/>${props.address}<br/>${props.bedrooms ?? '?'}室 / ${props.bathrooms ?? '?'}水回り`

      if (mode === 'buyer-ability' && selectedUser?.budget_max) {
        const budget = selectedUser.budget_max
        const label = price <= budget ? '予算内' : price <= budget * 1.15 ? 'やや超過' : '予算超過'
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

      const marketGeojson = toPropertyGeoJSON(properties)
      const holdingsGeojson = toHoldingGeoJSON(holdings)
      const shouldShowHoldings = mode === 'properties' && holdingsGeojson.features.length > 0
      const activeGeojson = shouldShowHoldings ? holdingsGeojson : marketGeojson
      if (activeGeojson.features.length === 0) return

      if (mode === 'properties' && shouldShowHoldings) {
        map.addSource(HOLDING_SOURCE_ID, {
          type: 'geojson',
          data: holdingsGeojson,
        })

        map.addLayer({
          id: 'holdings-points',
          type: 'circle',
          source: HOLDING_SOURCE_ID,
          paint: {
            'circle-color': '#0f766e',
            'circle-radius': 9,
            'circle-stroke-width': 2,
            'circle-stroke-color': '#ffffff',
          },
        })

        map.on('click', 'holdings-points', handleClick as unknown as (e: maplibregl.MapMouseEvent) => void)
        map.on('mouseenter', 'holdings-points', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'holdings-points', () => { map.getCanvas().style.cursor = '' })
      } else if (mode === 'properties') {
        map.addSource(MARKET_SOURCE_ID, {
          type: 'geojson',
          data: marketGeojson,
          cluster: true,
          clusterMaxZoom: 14,
          clusterRadius: 50,
        })

        map.addLayer({
          id: 'props-clusters',
          type: 'circle',
          source: MARKET_SOURCE_ID,
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
          source: MARKET_SOURCE_ID,
          filter: ['has', 'point_count'],
          layout: { 'text-field': '{point_count_abbreviated}', 'text-size': 13 },
          paint: { 'text-color': '#ffffff' },
        })

        map.addLayer({
          id: 'props-points',
          type: 'circle',
          source: MARKET_SOURCE_ID,
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
            const zoom = await (map.getSource(MARKET_SOURCE_ID) as maplibregl.GeoJSONSource).getClusterExpansionZoom(clusterId)
            map.easeTo({ center: (features[0].geometry as GeoJSON.Point).coordinates as [number, number], zoom })
          } catch { /* ignore */ }
        })
      } else if (mode === 'heatmap') {
        map.addSource(MARKET_SOURCE_ID, { type: 'geojson', data: marketGeojson })

        const prices = marketGeojson.features.map((f) => f.properties!.asking_price as number)
        const minPrice = Math.min(...prices)
        const maxPrice = Math.max(...prices)

        map.addLayer({
          id: 'props-heatmap',
          type: 'heatmap',
          source: MARKET_SOURCE_ID,
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
        map.addSource(MARKET_SOURCE_ID, { type: 'geojson', data: marketGeojson })

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
          source: MARKET_SOURCE_ID,
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
      const coords = activeGeojson.features.map(
        (f) => (f.geometry as GeoJSON.Point).coordinates as [number, number],
      )
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
  }, [mode, properties, holdings, selectedUser, handleClick])

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
            {m === 'properties' ? '物件' : m === 'heatmap' ? '価格ヒートマップ' : '予算比較'}
          </button>
        ))}
      </div>

      {/* Buyer ability overlay when no user selected */}
      {mode === 'buyer-ability' && !selectedUser?.budget_max && (
        <div className="map-overlay-message">投資家プロフィールを選択すると予算比較を表示できます</div>
      )}

      {/* Budget legend */}
      {mode === 'buyer-ability' && selectedUser?.budget_max && (
        <div className="map-legend">
          <div className="map-legend-title">予算上限: {formatJpyCompact(selectedUser.budget_max)}</div>
          <div className="map-legend-item"><span className="map-legend-dot map-legend-dot--success" />予算内</div>
          <div className="map-legend-item"><span className="map-legend-dot map-legend-dot--budget" />+15% まで</div>
          <div className="map-legend-item"><span className="map-legend-dot map-legend-dot--danger" />予算超過</div>
        </div>
      )}

      <div ref={containerRef} className="dashboard-map-canvas" />
    </div>
  )
}
