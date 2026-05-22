export interface PublicRuntimeConfig {
  environment: string
  api_base_url: string
  ws_base_url: string
  supabase_url: string
  supabase_publishable_key: string
  map_style_url: string
}

const DEFAULT_RUNTIME_CONFIG: PublicRuntimeConfig = {
  environment: 'development',
  api_base_url: '/api',
  ws_base_url: '/ws',
  supabase_url: '',
  supabase_publishable_key: '',
  map_style_url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
}

let cachedRuntimeConfig: PublicRuntimeConfig = DEFAULT_RUNTIME_CONFIG
let runtimeConfigPromise: Promise<PublicRuntimeConfig> | null = null

function normalizeConfig(
  config: Partial<PublicRuntimeConfig> | undefined,
): PublicRuntimeConfig {
  return {
    environment: config?.environment || DEFAULT_RUNTIME_CONFIG.environment,
    api_base_url: config?.api_base_url || DEFAULT_RUNTIME_CONFIG.api_base_url,
    ws_base_url: config?.ws_base_url || DEFAULT_RUNTIME_CONFIG.ws_base_url,
    supabase_url: config?.supabase_url || '',
    supabase_publishable_key: config?.supabase_publishable_key || '',
    map_style_url: config?.map_style_url || DEFAULT_RUNTIME_CONFIG.map_style_url,
  }
}

function joinPath(basePath: string, suffix: string): string {
  const normalizedBase = basePath.endsWith('/') ? basePath.slice(0, -1) : basePath
  const normalizedSuffix = suffix.startsWith('/') ? suffix : `/${suffix}`
  return `${normalizedBase}${normalizedSuffix}`
}

export async function loadRuntimeConfig(): Promise<PublicRuntimeConfig> {
  if (runtimeConfigPromise) {
    return runtimeConfigPromise
  }

  runtimeConfigPromise = fetch('/api/config/public', {
    headers: { Accept: 'application/json' },
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Failed to load runtime config (${response.status})`)
      }
      const data = await response.json() as Partial<PublicRuntimeConfig>
      cachedRuntimeConfig = normalizeConfig(data)
      return cachedRuntimeConfig
    })
    .catch(() => {
      cachedRuntimeConfig = DEFAULT_RUNTIME_CONFIG
      return cachedRuntimeConfig
    })

  return runtimeConfigPromise
}

export function getRuntimeConfig(): PublicRuntimeConfig {
  return cachedRuntimeConfig
}

export function isSupabaseConfigured(): boolean {
  const config = getRuntimeConfig()
  return Boolean(config.supabase_url && config.supabase_publishable_key)
}

export function buildApiUrl(path: string): string {
  const base = getRuntimeConfig().api_base_url || DEFAULT_RUNTIME_CONFIG.api_base_url
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  if (/^https?:\/\//.test(base)) {
    return `${base.replace(/\/$/, '')}${normalizedPath}`
  }

  return joinPath(base, normalizedPath)
}

export function buildRootUrl(path: string): string {
  const base = getRuntimeConfig().api_base_url || DEFAULT_RUNTIME_CONFIG.api_base_url
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  if (/^https?:\/\//.test(base)) {
    const url = new URL(base)
    return `${url.origin}${normalizedPath}`
  }

  return normalizedPath
}

export function buildWebSocketUrl(path: string): string {
  const base = getRuntimeConfig().ws_base_url || DEFAULT_RUNTIME_CONFIG.ws_base_url
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  if (/^wss?:\/\//.test(base)) {
    return `${base.replace(/\/$/, '')}${normalizedPath}`
  }

  if (/^https?:\/\//.test(base)) {
    const url = new URL(base)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    url.pathname = joinPath(url.pathname, normalizedPath)
    return url.toString()
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${joinPath(base, normalizedPath)}`
}
