import { getAccessToken } from './supabase'

const BASE_URL = '/api'

async function buildHeaders(extra?: HeadersInit): Promise<HeadersInit> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = await getAccessToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return { ...headers, ...(extra as Record<string, string> | undefined) }
}

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const headers = await buildHeaders(options?.headers)
  const response = await fetch(`${BASE_URL}${url}`, { ...options, headers })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || 'Request failed')
  }
  return response.json()
}

async function fetchRootJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const headers = await buildHeaders(options?.headers)
  const response = await fetch(url, { ...options, headers })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || 'Request failed')
  }
  return response.json()
}

export const api = {
  properties: {
    list: (params?: Record<string, string>) => {
      const qs = params ? '?' + new URLSearchParams(params).toString() : ''
      return fetchJSON<{ properties: unknown[]; count: number }>(`/properties/${qs}`)
    },
    get: (id: string) => fetchJSON(`/properties/${id}`),
  },
  users: {
    list: () => fetchJSON<Array<{
      id: string
      name: string
      email: string
      role: string
      budget_min?: number | null
      budget_max?: number | null
      life_stage?: string | null
      investment_goals: Record<string, unknown>
      risk_tolerance?: string | null
      timeline_days?: number | null
      latitude?: number | null
      longitude?: number | null
      zip_code?: string | null
      search_radius?: number | null
      preferred_types: string[]
      created_at?: string | null
    }>>('/users/'),
    get: (id: string) => fetchJSON<{
      id: string
      name: string
      email: string
      role: string
      budget_min?: number | null
      budget_max?: number | null
      life_stage?: string | null
      investment_goals: Record<string, unknown>
      risk_tolerance?: string | null
      timeline_days?: number | null
      latitude?: number | null
      longitude?: number | null
      zip_code?: string | null
      search_radius?: number | null
      preferred_types: string[]
      created_at?: string | null
    }>(`/users/${id}`),
    create: (data: {
      name: string
      email: string
      role?: string
      budget_min?: number | null
      budget_max?: number | null
      life_stage?: string | null
      investment_goals?: Record<string, unknown>
      risk_tolerance?: string
      timeline_days?: number
      latitude?: number | null
      longitude?: number | null
      zip_code?: string | null
      search_radius?: number
      preferred_types?: string[]
    }) => fetchJSON<{ id: string }>('/users/', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, unknown>) =>
      fetchJSON(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) => fetchJSON(`/users/${id}`, { method: 'DELETE' }),
  },
  agent: {
    message: (data: { user_id: string; role: string; message: string; report_id?: string | null }) =>
      fetchJSON<{ response: string; tool_calls: Array<{ tool: string; input: unknown; output: unknown }>; error?: string | null }>('/agent/message', { method: 'POST', body: JSON.stringify(data) }),
  },
  portfolio: {
    list: (userId: string) =>
      fetchJSON<import('./types').InvestorPortfolio[]>(`/portfolio/?user_id=${encodeURIComponent(userId)}`),
    create: (data: { user_id: string; name: string; investment_strategy?: string; notes?: string }) =>
      fetchJSON<import('./types').InvestorPortfolio>('/portfolio/', { method: 'POST', body: JSON.stringify(data) }),
    get: (portfolioId: string) =>
      fetchJSON<import('./types').InvestorPortfolio>(`/portfolio/${portfolioId}`),
    delete: (portfolioId: string) =>
      fetchJSON(`/portfolio/${portfolioId}`, { method: 'DELETE' }),
    listHoldings: (portfolioId: string) =>
      fetchJSON<import('./types').PortfolioHolding[]>(`/portfolio/${portfolioId}/holdings`),
    addHolding: (portfolioId: string, data: import('./types').PortfolioHoldingCreate) =>
      fetchJSON<import('./types').PortfolioHolding>(`/portfolio/${portfolioId}/holdings`, { method: 'POST', body: JSON.stringify(data) }),
    deleteHolding: (portfolioId: string, holdingId: string) =>
      fetchJSON(`/portfolio/${portfolioId}/holdings/${holdingId}`, { method: 'DELETE' }),
    aggregate: (portfolioId: string) =>
      fetchJSON<import('./types').PortfolioAggregate>(`/portfolio/${portfolioId}/aggregate`),
    summary: (portfolioId: string) =>
      fetchJSON<import('./types').PortfolioSummaryReport>(`/portfolio/${portfolioId}/summary`),
    importCsv: (data: {
      user_id: string
      user_email?: string | null
      user_name?: string | null
      portfolio_name?: string
      investment_strategy?: string
      holdings: import('./types').PortfolioHoldingCreate[]
    }) =>
      fetchJSON<{
        portfolio_id: string
        inserted_count: number
        updated_count: number
        skipped: string[]
      }>(`/portfolio/import/csv`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    csvTemplate: () =>
      fetchJSON<{ columns: string[]; csv: string }>(
        `/portfolio/import/csv/template`,
      ),
    fromProperty: (data: {
      user_id: string
      user_email?: string | null
      user_name?: string | null
      property_id: string
      portfolio_name?: string
      investment_strategy?: string
    }) =>
      fetchJSON<{ id: string; user_id: string; name: string }>(
        `/portfolio/from-property`,
        { method: 'POST', body: JSON.stringify(data) },
      ),
    chatExtract: (data: {
      messages: { role: 'user' | 'assistant'; content: string }[]
    }) =>
      fetchJSON<{
        narration: string
        holdings: import('./types').PortfolioHoldingCreate[]
      }>(`/portfolio/import/chat`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    chatConfirm: (data: {
      user_id: string
      user_email?: string | null
      user_name?: string | null
      portfolio_name?: string
      investment_strategy?: string
      holdings: import('./types').PortfolioHoldingCreate[]
    }) =>
      fetchJSON<{
        portfolio_id: string
        inserted_count: number
        updated_count: number
        skipped: string[]
      }>(`/portfolio/import/chat/confirm`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },
  listing: {
    parse: (url: string) =>
      fetchJSON<{
        source: string
        zpid: string
        url: string
        address_hint: string
        state?: string | null
        zip_code?: string | null
      }>('/listing/parse', { method: 'POST', body: JSON.stringify({ url }) }),
  },
  underwrite: {
    run: (data: import('./types').UnderwriteRequest) =>
      fetchJSON<import('./types').UnderwriteResponse>('/underwrite', { method: 'POST', body: JSON.stringify(data) }),
    stressTest: (data: { base_inputs: import('./types').UnderwriteRequest; config?: import('./types').StressTestConfig }) =>
      fetchJSON<import('./types').StressTestResponse>('/underwrite/stress-test', { method: 'POST', body: JSON.stringify(data) }),
  },
  decisions: {
    holding: (holdingId: string) =>
      fetchJSON<import('./types').HoldingDecisionResponse>(`/decisions/holding/${holdingId}`),
  },
  strategy: {
    extract: (payload: { portfolio_id: string; text: string }) =>
      fetchJSON<import('./types').StrategyExtractResponse>('/strategy/extract', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    run: (payload: {
      portfolio_id: string
      text?: string
      profile?: import('./types').StrategyProfile
    }) =>
      fetchJSON<import('./types').StrategyRunStartResponse>('/strategy/run', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    status: (runId: string) =>
      fetchJSON<import('./types').StrategyRunRecord>(`/strategy/${runId}/status`),
    result: (runId: string) =>
      fetchJSON<import('./types').StrategyRunRecord>(`/strategy/${runId}/result`),
    recent: (userId: string, limit = 5) =>
      fetchJSON<import('./types').StrategyRunRecord[]>(
        `/strategy/recent?user_id=${encodeURIComponent(userId)}&limit=${limit}`,
      ),
  },
  onboarding: {
    state: (userId?: string) => {
      const qs = userId ? `?user_id=${encodeURIComponent(userId)}` : ''
      return fetchJSON<{
        user_id: string | null
        has_portfolio: boolean
        has_profile: boolean
      }>(`/onboarding/state${qs}`)
    },
  },
  investorProfile: {
    get: (userId: string) =>
      fetchJSON<import('./types').InvestorProfile>(
        `/investor-profile/?user_id=${encodeURIComponent(userId)}`,
      ),
    upsert: (data: import('./types').InvestorProfileUpsert) =>
      fetchJSON<import('./types').InvestorProfile>(`/investor-profile/`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },
  recommendations: {
    list: (userId: string, topN = 10) =>
      fetchJSON<{
        recommendations: import('./types').PropertyRecommendation[]
        profile_id: string | null
        candidates_considered: number
      }>(
        `/properties/recommend?user_id=${encodeURIComponent(userId)}&top_n=${topN}`,
      ),
  },
  system: {
    health: () => fetchRootJSON<{ status: string; version: string }>('/health'),
    metrics: () => fetchRootJSON<{
      counters: Record<string, number>
      gauges: Record<string, number>
      histograms: Record<string, Record<string, number>>
    }>('/metrics'),
  },
}
