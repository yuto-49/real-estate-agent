import { useEffect, useRef, useState, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { api } from '../utils/api'
import type { Property, UserProfile, SimulationResult } from '../utils/types'

type MapMode = 'properties' | 'heatmap' | 'simulation' | 'buyer-ability'

interface SimSummary {
  property_id: string
  outcome: string
  final_price: number | null
  rounds_completed: number
  run_count: number
  accepted_count: number
}

interface Props {
  properties: Property[]
  selectedUser: UserProfile | null
  onPropertyClick?: (property: Property) => void
  simulationResults?: SimulationResult[]
}

const BASEMAP = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
const SOURCE_ID = 'properties'

interface SimLike {
  property_id: string
  outcome: string
  final_price: number | null
  rounds_completed: number
  created_at?: string
}

function buildSimSummaryMap(items: SimLike[]): Map<string, SimSummary> {
  const grouped = new Map<string, SimLike[]>()
  for (const row of items) {
    if (!row.property_id) continue
    if (!grouped.has(row.property_id)) grouped.set(row.property_id, [])
    grouped.get(row.property_id)!.push(row)
  }

  const out = new Map<string, SimSummary>()
  for (const [propertyId, rows] of grouped) {
    const sorted = [...rows].sort((a, b) => {
      const bt = b.created_at ? new Date(b.created_at).getTime() : 0
      const at = a.created_at ? new Date(a.created_at).getTime() : 0
      return bt - at
    })
    const latest = sorted[0]
    out.set(propertyId, {
      property_id: propertyId,
      outcome: latest.outcome,
      final_price: latest.final_price,
      rounds_completed: latest.rounds_completed,
      run_count: rows.length,
      accepted_count: rows.filter((r) => r.outcome === 'accepted').length,
    })
  }
  return out
}

function toGeoJSON(
  properties: Property[],
  simMap?: Map<string, SimSummary>,
): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: properties
      .filter((p) => p.latitude && p.longitude)
      .map((p) => {
        const sim = simMap?.get(p.id)
        return {
          type: 'Feature' as const,
          geometry: { type: 'Point' as const, coordinates: [p.longitude!, p.latitude!] },
          properties: {
            id: p.id,
            address: p.address,
            asking_price: p.asking_price,
            bedrooms: p.bedrooms ?? null,
            bathrooms: p.bathrooms ?? null,
            property_type: p.property_type ?? '',
            // simulation fields (default to "none" if no sim)
            sim_outcome: sim?.outcome ?? 'none',
            sim_final_price: sim?.final_price ?? 0,
            sim_rounds: sim?.rounds_completed ?? 0,
            sim_discount: sim?.final_price
              ? Math.round(((p.asking_price - sim.final_price) / p.asking_price) * 100)
              : 0,
            sim_runs: sim?.run_count ?? 0,
            sim_deals: sim?.accepted_count ?? 0,
            has_sim: sim ? 1 : 0,
          },
        }
      }),
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

export default function DashboardMap({ properties, selectedUser, onPropertyClick, simulationResults }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const mapLoaded = useRef(false)
  const popupRef = useRef<maplibregl.Popup | null>(null)
  const [mode, setMode] = useState<MapMode>('properties')
  const [simData, setSimData] = useState<Map<string, SimSummary>>(new Map())
  const simLoading = false // No longer async — data comes from props

  // Build sim data map from props or fallback to in-memory API
  useEffect(() => {
    if (mode !== 'simulation') return

    if (simulationResults !== undefined) {
      // Use DB-persisted results from props (including empty arrays).
      setSimData(buildSimSummaryMap(simulationResults))
    } else {
      // Fallback: fetch from in-memory store for backward compat
      api.simulation.list({ status: 'completed' }).then((sims) => {
        setSimData(buildSimSummaryMap(sims.map((s) => ({
          property_id: s.property_id,
          outcome: s.outcome,
          final_price: s.final_price,
          rounds_completed: s.rounds_completed,
          created_at: s.created_at,
        }))))
      }).catch(() => {
        setSimData(new Map())
      })
    }
  }, [mode, simulationResults])

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

      if (mode === 'simulation') {
        const outcome = String(props.sim_outcome)
        const finalPrice = Number(props.sim_final_price)
        const rounds = Number(props.sim_rounds)
        const discount = Number(props.sim_discount)
        const runs = Number(props.sim_runs)
        const deals = Number(props.sim_deals)
        if (outcome !== 'none') {
          const outcomeLabel = outcome === 'accepted' ? 'Deal Reached'
            : outcome === 'rejected' ? 'Rejected'
            : outcome === 'max_rounds' ? 'Max Rounds (No Deal)'
            : outcome
          html += `<br/><strong style="color:${outcome === 'accepted' ? '#16a34a' : '#dc2626'}">${outcomeLabel}</strong>`
          if (finalPrice) html += `<br/>Final: $${finalPrice.toLocaleString()} (${discount > 0 ? discount + '% below' : Math.abs(discount) + '% above'} asking)`
          html += `<br/>Rounds: ${rounds}`
          if (runs > 0) html += `<br/>Simulation Runs: ${runs} (Deals: ${deals})`
          html += `<br/><a href="/simulation/visualize/${props.id}" style="color:#3b82f6;font-size:12px;text-decoration:underline">View Replay</a>`
        } else {
          html += `<br/><em style="color:#999">No simulation run</em>`
        }
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
    // Don't render simulation mode while still loading
    if (mode === 'simulation' && simLoading) return

    const apply = () => {
      removeLayers(map)
      popupRef.current?.remove()

      const geojson = toGeoJSON(properties, mode === 'simulation' ? simData : undefined)
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
      } else if (mode === 'simulation') {
        map.addSource(SOURCE_ID, { type: 'geojson', data: geojson })

        const hasAnySim = geojson.features.some((f) => f.properties!.has_sim === 1)

        if (!hasAnySim) {
          // No simulations — show all as grey
          map.addLayer({
            id: 'props-sim-none',
            type: 'circle',
            source: SOURCE_ID,
            paint: {
              'circle-color': '#999999',
              'circle-radius': 10,
              'circle-stroke-width': 2,
              'circle-stroke-color': '#ffffff',
            },
          })
          map.on('click', 'props-sim-none', handleClick as unknown as (e: maplibregl.MapMouseEvent) => void)
          map.on('mouseenter', 'props-sim-none', () => { map.getCanvas().style.cursor = 'pointer' })
          map.on('mouseleave', 'props-sim-none', () => { map.getCanvas().style.cursor = '' })
        } else {
          // Color by outcome
          map.addLayer({
            id: 'props-sim-circles',
            type: 'circle',
            source: SOURCE_ID,
            paint: {
              'circle-color': [
                'match', ['get', 'sim_outcome'],
                'accepted', '#22c55e',    // green — deal
                'rejected', '#ef4444',    // red — rejected
                'max_rounds', '#f59e0b',  // amber — stalemate
                'broker_stopped', '#f97316', // orange — broker intervened
                '#94a3b8',                // grey — no sim
              ] as unknown as maplibregl.ExpressionSpecification,
              'circle-radius': [
                'case',
                ['==', ['get', 'has_sim'], 1], 11,
                7,
              ] as unknown as maplibregl.ExpressionSpecification,
              'circle-stroke-width': 2,
              'circle-stroke-color': '#ffffff',
              'circle-opacity': [
                'case',
                ['==', ['get', 'has_sim'], 1], 1,
                0.5,
              ] as unknown as maplibregl.ExpressionSpecification,
            },
          })

          // Overlay: heatmap weighted by negotiation discount (properties where deals were made at bigger discounts glow hotter)
          const simFeatures = geojson.features.filter((f) => f.properties!.has_sim === 1 && f.properties!.sim_final_price > 0)
          if (simFeatures.length > 0) {
            const simGeoJSON: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: simFeatures }
            map.addSource('sim-heat', { type: 'geojson', data: simGeoJSON })

            const discounts = simFeatures.map((f) => Math.abs(f.properties!.sim_discount as number))
            const maxDiscount = Math.max(...discounts, 1)

            map.addLayer({
              id: 'props-sim-heat',
              type: 'heatmap',
              source: 'sim-heat',
              paint: {
                'heatmap-weight': ['interpolate', ['linear'], ['abs', ['get', 'sim_discount']], 0, 0.1, maxDiscount, 1],
                'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 0.5, 15, 2],
                'heatmap-color': [
                  'interpolate', ['linear'], ['heatmap-density'],
                  0, 'rgba(34,197,94,0)',
                  0.2, 'rgba(34,197,94,0.15)',
                  0.4, 'rgba(250,204,21,0.3)',
                  0.7, 'rgba(249,115,22,0.5)',
                  1, 'rgba(239,68,68,0.6)',
                ],
                'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 4, 15, 30],
                'heatmap-opacity': 0.6,
              },
            })
          }

          map.on('click', 'props-sim-circles', handleClick as unknown as (e: maplibregl.MapMouseEvent) => void)
          map.on('mouseenter', 'props-sim-circles', () => { map.getCanvas().style.cursor = 'pointer' })
          map.on('mouseleave', 'props-sim-circles', () => { map.getCanvas().style.cursor = '' })
        }
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
  }, [mode, properties, selectedUser, simData, simLoading, handleClick])

  // Clean up sim-heat source on layer removal
  useEffect(() => {
    return () => {
      const map = mapRef.current
      if (map?.getSource('sim-heat')) {
        if (map.getLayer('props-sim-heat')) map.removeLayer('props-sim-heat')
        map.removeSource('sim-heat')
      }
    }
  }, [mode])

  const simCount = simData.size
  const propertyIds = new Set(properties.map((p) => p.id))
  const unlinkedSimCount = [...simData.keys()].filter((id) => !propertyIds.has(id)).length
  const linkedSimCount = Math.max(0, simCount - unlinkedSimCount)
  const totalSimRuns = [...simData.values()].reduce((sum, s) => sum + s.run_count, 0)
  const dealCount = [...simData.values()].reduce((sum, s) => sum + s.accepted_count, 0)

  return (
    <div className="dashboard-map-area">
      {/* Mode toggle */}
      <div className="map-mode-toggle">
        {(['properties', 'heatmap', 'simulation', 'buyer-ability'] as MapMode[]).map((m) => (
          <button
            key={m}
            className={mode === m ? 'active' : ''}
            onClick={() => setMode(m)}
          >
            {m === 'properties' ? 'Properties' : m === 'heatmap' ? 'Heatmap' : m === 'simulation' ? 'Simulation' : 'Budget'}
          </button>
        ))}
      </div>

      {/* Simulation loading */}
      {mode === 'simulation' && simLoading && (
        <div className="map-overlay-message">Loading simulation data...</div>
      )}

      {/* Simulation: no data */}
      {mode === 'simulation' && !simLoading && simCount === 0 && (
        <div className="map-overlay-message">No completed simulations yet. Run a simulation from the Simulation page.</div>
      )}

      {mode === 'simulation' && !simLoading && simCount > 0 && unlinkedSimCount > 0 && (
        <div className="map-overlay-message" style={{ top: '4.5rem', bottom: 'auto', background: 'rgba(255, 244, 229, 0.92)', color: '#9a3412' }}>
          {unlinkedSimCount} simulation result set(s) are not linked to current map properties. Use a real property from the selector when starting simulations.
        </div>
      )}

      {/* Simulation legend */}
      {mode === 'simulation' && !simLoading && simCount > 0 && (
        <div className="map-legend">
          <div className="map-legend-title">Simulation Results (linked: {linkedSimCount}, runs: {totalSimRuns})</div>
          <div className="map-legend-item"><span className="map-legend-dot" style={{ background: '#22c55e' }} />Deals Reached ({dealCount})</div>
          <div className="map-legend-item"><span className="map-legend-dot" style={{ background: '#f59e0b' }} />Max Rounds (Stalemate)</div>
          <div className="map-legend-item"><span className="map-legend-dot" style={{ background: '#ef4444' }} />Rejected</div>
          <div className="map-legend-item"><span className="map-legend-dot" style={{ background: '#f97316' }} />Broker Stopped</div>
          <div className="map-legend-item"><span className="map-legend-dot" style={{ background: '#94a3b8' }} />Not Simulated</div>
          <div className="map-legend-divider" />
          <div className="map-legend-item" style={{ fontSize: '0.72rem', color: '#888' }}>Heatmap glow = negotiation discount</div>
        </div>
      )}

      {/* Buyer ability overlay when no user selected */}
      {mode === 'buyer-ability' && !selectedUser?.budget_max && (
        <div className="map-overlay-message">Select a buyer to see purchase ability</div>
      )}

      {/* Budget legend */}
      {mode === 'buyer-ability' && selectedUser?.budget_max && (
        <div className="map-legend">
          <div className="map-legend-title">Budget: ${selectedUser.budget_max.toLocaleString()}</div>
          <div className="map-legend-item"><span className="map-legend-dot" style={{ background: '#22c55e' }} />Within Budget</div>
          <div className="map-legend-item"><span className="map-legend-dot" style={{ background: '#eab308' }} />Stretch (up to +15%)</div>
          <div className="map-legend-item"><span className="map-legend-dot" style={{ background: '#ef4444' }} />Over Budget</div>
        </div>
      )}

      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  )
}
