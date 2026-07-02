import type {
  Negotiation,
  NegotiationAcceptRequest,
  NegotiationMutationResponse,
  NegotiationOfferRequest,
  NegotiationSession,
  SocialSimAction,
  SocialSimResult,
  SocialSimStartRequest,
  SocialSimStartResponse,
  SocialSimStatus,
  SocialSimTimelineResponse,
  NegotiationTransitionRequest,
} from './types'
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
    marketContext: (id: string) =>
      fetchJSON<import('./types').MarketContextSnapshot>(`/properties/${id}/market-context`),
  },
  signals: {
    reinfolib: (params: { zip_code?: string; types?: string }) => {
      const qs = new URLSearchParams()
      if (params.zip_code) qs.set('zip_code', params.zip_code)
      if (params.types) qs.set('types', params.types)
      return fetchJSON<import('./types').MarketContextSnapshot>(
        `/signals/reinfolib?${qs.toString()}`,
      )
    },
  },
  negotiations: {
    start: (data: { property_id: string; buyer_id: string; seller_id: string }) =>
      fetchJSON<Negotiation>('/negotiations/', { method: 'POST', body: JSON.stringify(data) }),
    get: (id: string) => fetchJSON<NegotiationSession>(`/negotiations/${id}`),
    offer: (id: string, data: NegotiationOfferRequest) =>
      fetchJSON<NegotiationMutationResponse>(`/negotiations/${id}/offer`, { method: 'POST', body: JSON.stringify(data) }),
    accept: (id: string, data: NegotiationAcceptRequest) =>
      fetchJSON<NegotiationMutationResponse>(`/negotiations/${id}/accept`, { method: 'POST', body: JSON.stringify(data) }),
    transition: (id: string, data: NegotiationTransitionRequest) =>
      fetchJSON<NegotiationMutationResponse>(`/negotiations/${id}/transition`, { method: 'POST', body: JSON.stringify(data) }),
  },
  reports: {
    generate: (data: {
      user_id: string;
      question?: string;
      zip_code?: string;
      latitude?: number;
      longitude?: number;
      min_price?: number;
      max_price?: number;
      property_type?: string;
    }) =>
      fetchJSON<{ id: string; user_id: string; status: string; created_at?: string }>('/reports/generate', { method: 'POST', body: JSON.stringify(data) }),
    status: (id: string) => fetchJSON<{ id: string; user_id: string; status: string; progress: number; current_step: string; step_key?: string; created_at?: string; error_message?: string | null }>(`/reports/status/${id}`),
    get: (id: string) => fetchJSON<{ id: string; user_id: string; status: string; report_json: Record<string, unknown> }>(`/reports/${id}`),
    listByUser: (userId: string) => fetchJSON<Array<{ id: string; user_id: string; status: string; progress: number; current_step: string; step_key?: string; created_at?: string; error_message?: string | null }>>(`/reports/user/${userId}`),
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
  socialSim: {
    start: (data: SocialSimStartRequest) =>
      fetchJSON<SocialSimStartResponse>('/social-sim/start', { method: 'POST', body: JSON.stringify(data) }),
    status: (runId: string) => fetchJSON<SocialSimStatus>(`/social-sim/${runId}/status`),
    result: (runId: string) => fetchJSON<SocialSimResult>(`/social-sim/${runId}/result`),
    actions: (runId: string, params?: { round_num?: number; topic?: string; limit?: number; offset?: number }) => {
      const search = new URLSearchParams()
      if (params?.round_num != null) search.set('round_num', String(params.round_num))
      if (params?.topic) search.set('topic', params.topic)
      if (params?.limit != null) search.set('limit', String(params.limit))
      if (params?.offset != null) search.set('offset', String(params.offset))
      const query = search.toString()
      return fetchJSON<SocialSimAction[]>(`/social-sim/${runId}/actions${query ? `?${query}` : ''}`)
    },
    timeline: (runId: string) => fetchJSON<SocialSimTimelineResponse>(`/social-sim/${runId}/timeline`),
    generateReport: (runId: string, data: { property_id: string; household_id: string }) =>
      fetchJSON<{ report_id: string; message: string }>(`/social-sim/${runId}/generate-report`, { method: 'POST', body: JSON.stringify(data) }),
  },
  simulation: {
    start: (data: {
      property_id: string;
      buyer_user_id: string;
      seller_user_id: string;
      initial_offer: number;
      asking_price: number;
      seller_minimum: number;
      buyer_maximum: number;
      strategy?: string;
      max_rounds?: number;
      report_id?: string;
    }) => fetchJSON<{ id: string; status: string; message: string }>('/simulation/start', { method: 'POST', body: JSON.stringify(data) }),
    status: (id: string) => fetchJSON<{
      id: string; status: string; current_round: number; max_rounds: number;
      progress: number; transcript: Array<Record<string, unknown>>; created_at?: string;
    }>(`/simulation/status/${id}`),
    result: (id: string) => fetchJSON<{
      id: string; status: string; outcome: string; final_price: number | null;
      rounds_completed: number; transcript: Array<Record<string, unknown>>;
      summary: Record<string, unknown>; created_at?: string;
    }>(`/simulation/result/${id}`),
    list: (params?: { property_id?: string; status?: string }) => {
      const qs = params ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v) as string[][]).toString() : ''
      return fetchJSON<Array<{
        id: string; property_id: string; status: string; outcome: string;
        final_price: number | null; rounds_completed: number; max_rounds: number;
        created_at?: string;
      }>>(`/simulation/list${qs}`)
    },
    // Batch simulation
    generatePersonas: (data: { buyer_profile: Record<string, unknown>; property_context: Record<string, unknown> }) =>
      fetchJSON<{ buyer: Record<string, unknown>; seller: Record<string, unknown> }>('/simulation/personas', { method: 'POST', body: JSON.stringify(data) }),
    getScenarios: () => fetchJSON<{ scenarios: Array<{ name: string; description: string; constraints: Record<string, unknown>; max_rounds: number }> }>('/simulation/scenarios'),
    batchStart: (data: {
      property_id: string;
      asking_price: number;
      initial_offer: number;
      seller_minimum: number;
      buyer_maximum: number;
      max_rounds?: number;
      buyer_user_id?: string;
      seller_user_id?: string;
      strategy?: string;
      scenario_names: string[];
      report_id?: string;
      persona_data?: Record<string, unknown>;
    }) => fetchJSON<{ batch_id: string; status: string; total_scenarios: number; message: string }>('/simulation/batch/start', { method: 'POST', body: JSON.stringify(data) }),
    batchStatus: (batchId: string) => fetchJSON<Record<string, unknown>>(`/simulation/batch/status/${batchId}`),
    batchResult: (batchId: string) => fetchJSON<Record<string, unknown>>(`/simulation/batch/result/${batchId}`),
    // DB-persisted simulation results
    savedResults: (params?: { user_id?: string }) => {
      const qs = params ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v) as string[][]).toString() : ''
      return fetchJSON<{ results: Array<{
        id: string; user_id: string; property_id: string; batch_id: string | null;
        scenario_name: string | null; outcome: string; final_price: number | null;
        asking_price: number; initial_offer: number; rounds_completed: number;
        max_rounds: number; strategy: string; summary: Record<string, unknown>;
        price_path: Array<{ round: number; role: string; price: number }>; created_at: string;
      }>; count: number }>(`/simulation/results${qs}`)
    },
    savedResult: (id: string) => fetchJSON<{
      id: string; user_id: string; property_id: string; batch_id: string | null;
      scenario_name: string | null; outcome: string; final_price: number | null;
      asking_price: number; initial_offer: number; rounds_completed: number;
      max_rounds: number; strategy: string; summary: Record<string, unknown>;
      price_path: Array<{ round: number; role: string; price: number }>; created_at: string;
    }>(`/simulation/results/${id}`),
    // Unified simulation engine
    runUnified: (data: {
      holding_id: string
      portfolio_id: string
      max_rounds: number
      shocks: Array<{ round_num: number; shock_type: string; magnitude: number; label: string }>
      convergence_threshold: number
    }) =>
      fetchJSON<{
        run_id: string
        status: string
        recommendation: string
        converged: boolean
        converged_at_round: number | null
        final_noi: number
        final_dscr: number
        final_cap_rate: number
        final_occupancy: number
        rounds_count: number
      }>('/simulation/run', { method: 'POST', body: JSON.stringify(data) }),
    replayUnified: (runId: string) =>
      fetchJSON<{
        run_id: string
        rounds: Array<{
          round_num: number
          noi: number
          occupancy: number
          dscr: number
          cap_rate: number
          recommendation: string
          shocks: string[]
          churn_avg: number
        }>
        converged: boolean
        converged_at_round: number | null
      }>(`/simulation/${runId}/replay`),
  },
  marketSimulation: {
    generatePersonas: (data: {
      investor_count: number
      cohort_preset: string
      scope?: Partial<import("./types").MarketSimulationScope>
    }) => fetchJSON<import("./types").MarketSimulationPersonaResponse>("/simulation/market/personas", { method: "POST", body: JSON.stringify(data) }),
    start: (data: {
      investor_count: number
      tick_count: number
      cohort_preset: string
      run_label?: string
      scope?: Partial<import("./types").MarketSimulationScope>
      seeded_personas?: import("./types").MarketInvestorPersona[]
    }) => fetchJSON<import("./types").MarketSimulationStartResponse>("/simulation/market/start", { method: "POST", body: JSON.stringify(data) }),
    status: (runId: string) => fetchJSON<import("./types").MarketSimulationRunStatus>(`/simulation/market/status/${runId}`),
    result: (runId: string) => fetchJSON<import("./types").MarketSimulationRunResult>(`/simulation/market/result/${runId}`),
    replay: (runId: string) => fetchJSON<import("./types").MarketSimulationReplay>(`/simulation/market/replay/${runId}`),
    handoffToNegotiation: (data: { run_id: string; investor_id: string; property_id: string; max_rounds?: number }) =>
      fetchJSON<import("./types").MarketSimulationHandoffResponse>("/simulation/market/handoff-to-negotiation", { method: "POST", body: JSON.stringify(data) }),
  },
  visualization: {
    getProperty: (propertyId: string) =>
      fetchJSON<import('./types').PropertyVisualization>(`/visualization/property/${propertyId}`),
    getReplay: (simulationId: string) =>
      fetchJSON<import('./types').SimulationReplay>(`/visualization/replay/${simulationId}`),
    getBatchReplays: (batchId: string) =>
      fetchJSON<{ replays: import('./types').SimulationReplay[]; count: number }>(`/visualization/replay/batch/${batchId}`),
    getPropertyReplays: (propertyId: string, limit = 5) =>
      fetchJSON<{ replays: import('./types').SimulationReplay[]; count: number }>(`/visualization/replay/by-property/${propertyId}?limit=${limit}`),
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
        property_id: string
        url: string
        address_hint: string
        prefecture?: string | null
        postal_code?: string | null
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
  satei: {
    compute: (data: {
      city_code?: string; zip_code?: string; address?: string;
      menseki_m2?: number; built_year?: number; construction_type?: string;
      walk_minutes?: number; property_id?: string; user_id?: string;
      overrides?: Record<string, Record<string, number>>;
    }) =>
      fetchJSON<{
        session_id: string | null; satei_price_yen: number;
        confidence_low_yen: number; confidence_high_yen: number;
        comp_count: number; method: string;
        comps: Array<{
          comp_id: string; address_hint: string | null;
          raw_price_yen: number; adjusted_price_yen: number;
          menseki_m2: number | null; built_year: number | null;
          construction_type: string | null; walk_minutes: number | null;
          transaction_year: number | null; transaction_quarter: number | null;
          adjustments: Array<{ factor_name: string; comp_value: unknown; subject_value: unknown; adjustment_pct: number }>;
          total_adjustment_pct: number;
        }>;
      }>('/satei/compute', { method: 'POST', body: JSON.stringify(data) }),
    get: (sessionId: string) =>
      fetchJSON<{
        session_id: string; satei_price_yen: number;
        confidence_low_yen: number; confidence_high_yen: number;
        comp_count: number; comps: unknown[]; method: string;
      }>(`/satei/${sessionId}`),
    listByUser: (userId: string) =>
      fetchJSON<Array<{
        id: string; address: string | null; satei_price_yen: number | null;
        comp_count: number | null; created_at: string | null;
      }>>(`/satei/user/${userId}`),
  },
  priceProbability: {
    compute: (data: {
      satei_price_yen: number;
      range_low_pct?: number; range_high_pct?: number; step_pct?: number;
      iterations?: number; avg_days_on_market?: number; demand_elasticity?: number;
    }) =>
      fetchJSON<{
        satei_price_yen: number; iterations_per_point: number;
        sweet_spot_yen: number | null; sweet_spot_pct: number | null;
        points: Array<{
          asking_price_yen: number; premium_pct: number;
          p30: number; p60: number; p90: number; p180: number;
          expected_days: number; expected_settlement_yen: number;
        }>;
      }>('/price-probability/compute', { method: 'POST', body: JSON.stringify(data) }),
  },
  rentComps: {
    get: (propertyId: string) =>
      fetchJSON<import('./types').RentValidationResponse>(
        `/properties/${propertyId}/rent-comps`,
      ),
    refresh: (propertyId: string) =>
      fetchJSON<{ status: string; message: string }>(
        `/properties/${propertyId}/rent-comps/refresh`,
        { method: 'POST' },
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
