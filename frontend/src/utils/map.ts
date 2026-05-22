import maplibregl from 'maplibre-gl'
import { getRuntimeConfig } from '../config/runtime'

const MAP_LOAD_TIMEOUT_MS = 12000

export interface ManagedMapController {
  map: maplibregl.Map
  destroy: () => void
}

interface CreateManagedMapOptions {
  container: HTMLDivElement
  center: [number, number]
  zoom: number
  navigationControlPosition?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'
  onLoad?: (map: maplibregl.Map) => void
  onError?: (message: string) => void
}

export function hasValidCoordinates(
  latitude?: number | null,
  longitude?: number | null,
): latitude is number {
  return (
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    Math.abs(Number(latitude)) <= 90 &&
    Math.abs(Number(longitude)) <= 180
  )
}

export function getValidCoordinates(
  latitude?: number | null,
  longitude?: number | null,
): { lat: number; lng: number } | null {
  if (!hasValidCoordinates(latitude, longitude)) {
    return null
  }

  return {
    lat: Number(latitude),
    lng: Number(longitude),
  }
}

export function getMapStyleUrl(): string {
  return getRuntimeConfig().map_style_url
}

export function createManagedMap({
  container,
  center,
  zoom,
  navigationControlPosition = 'top-right',
  onLoad,
  onError,
}: CreateManagedMapOptions): ManagedMapController {
  const map = new maplibregl.Map({
    container,
    style: getMapStyleUrl(),
    center,
    zoom,
  })

  map.addControl(new maplibregl.NavigationControl(), navigationControlPosition)

  let didLoad = false
  const loadTimeout = window.setTimeout(() => {
    if (!didLoad) {
      onError?.('Map tiles are taking too long to load. Check your network or map style configuration.')
    }
  }, MAP_LOAD_TIMEOUT_MS)

  const resizeMap = () => map.resize()
  const resizeObserver = new ResizeObserver(resizeMap)
  resizeObserver.observe(container)
  window.addEventListener('resize', resizeMap)

  map.on('load', () => {
    didLoad = true
    window.clearTimeout(loadTimeout)
    resizeMap()
    onLoad?.(map)
  })

  map.on('error', (event) => {
    if (didLoad) {
      return
    }
    const error = event.error
    const message = error instanceof Error ? error.message : 'Failed to load the map.'
    onError?.(message)
  })

  return {
    map,
    destroy: () => {
      window.clearTimeout(loadTimeout)
      resizeObserver.disconnect()
      window.removeEventListener('resize', resizeMap)
      map.remove()
    },
  }
}
