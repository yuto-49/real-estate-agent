const BASE_URL = '/api'

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || 'Request failed')
  }
  return response.json()
}

async function fetchRootJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
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
  negotiations: {
    start: (data: { property_id: string; buyer_id: string; seller_id: string }) =>
      fetchJSON('/negotiations/', { method: 'POST', body: JSON.stringify(data) }),
    get: (id: string) => fetchJSON(`/negotiations/${id}`),
    offer: (id: string, data: { offer_price: number; from_role: string; message?: string }) =>
      fetchJSON(`/negotiations/${id}/offer`, { method: 'POST', body: JSON.stringify(data) }),
    accept: (id: string, data: { from_role: string; final_price: number }) =>
      fetchJSON(`/negotiations/${id}/accept`, { method: 'POST', body: JSON.stringify(data) }),
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
    status: (id: string) => fetchJSON<{ id: string; user_id: string; status: string; progress: number; current_step: string; step_key?: string; created_at?: string }>(`/reports/status/${id}`),
    get: (id: string) => fetchJSON<{ id: string; user_id: string; status: string; report_json: Record<string, unknown> }>(`/reports/${id}`),
    listByUser: (userId: string) => fetchJSON<Array<{ id: string; user_id: string; status: string; progress: number; current_step: string; step_key?: string; created_at?: string }>>(`/reports/user/${userId}`),
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
