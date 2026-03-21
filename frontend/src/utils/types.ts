/**
 * TypeScript event types mirroring api/ws_events.py
 */

export enum WSEventType {
  NEGOTIATION_STATE_CHANGE = 'negotiation.state_change',
  OFFER_RECEIVED = 'offer.received',
  COUNTER_OFFER = 'counter_offer',
  AGENT_RESPONSE = 'agent.response',
  TIMEOUT_WARNING = 'timeout.warning',
  TIMEOUT_EXPIRED = 'timeout.expired',
  SYSTEM_ERROR = 'system.error',
  CONNECTION_ACK = 'connection.ack',
}

export interface WSEvent {
  type: WSEventType
  timestamp: string
  correlation_id?: string
}

export interface NegotiationStateChangeEvent extends WSEvent {
  type: WSEventType.NEGOTIATION_STATE_CHANGE
  negotiation_id: string
  old_status: string
  new_status: string
  round_count: number
}

export interface OfferReceivedEvent extends WSEvent {
  type: WSEventType.OFFER_RECEIVED
  offer_id: string
  property_id: string
  offer_price: number
  buyer_id: string
}

export interface CounterOfferEvent extends WSEvent {
  type: WSEventType.COUNTER_OFFER
  negotiation_id: string
  counter_price: number
  from_role: string
  message: string
}

export interface AgentResponseEvent extends WSEvent {
  type: WSEventType.AGENT_RESPONSE
  agent_type: string
  response: string
  tool_calls: Record<string, unknown>[]
}

export interface TimeoutWarningEvent extends WSEvent {
  type: WSEventType.TIMEOUT_WARNING
  negotiation_id: string
  deadline_at: string
  hours_remaining: number
}

export interface ConnectionAckEvent extends WSEvent {
  type: WSEventType.CONNECTION_ACK
  negotiation_id: string
  current_status: string
}

export interface Property {
  id: string
  address: string
  asking_price: number
  bedrooms?: number
  bathrooms?: number
  sqft?: number
  property_type?: string
  latitude?: number
  longitude?: number
  status?: string
}

export interface Negotiation {
  id: string
  property_id: string
  buyer_id: string
  seller_id: string
  status: string
  round_count: number
  final_price?: number
  deadline_at?: string
}

export interface UserProfile {
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
}

// ── Saved Simulation Result (DB-persisted) ──

export interface SimulationResult {
  id: string
  user_id: string
  property_id: string
  batch_id: string | null
  scenario_name: string | null
  outcome: string
  final_price: number | null
  asking_price: number
  initial_offer: number
  rounds_completed: number
  max_rounds: number
  strategy: string
  summary: Record<string, unknown>
  price_path: Array<{ round: number; role: string; price: number }>
  created_at: string
}

// ── Batch Simulation Types ──

export interface AgentPersona {
  role: string
  name: string
  personality_type: string
  negotiation_style: string
  risk_tolerance: string
  experience_level: string
  motivations: string[]
  background: string
  pressure_points: string[]
  strengths: string[]
}

export interface ScenarioVariant {
  name: string
  description: string
  constraints: Record<string, unknown>
  max_rounds: number
}

export interface BatchSimulationStatus {
  batch_id: string
  status: string
  total_scenarios: number
  completed_scenarios: number
  total_progress: number
  scenarios: Array<{
    scenario: string
    status: string
    current_round: number
    max_rounds: number
    progress: number
  }>
  created_at: string
}

export interface ScenarioOutcome {
  scenario: string
  description: string
  outcome: string
  final_price: number | null
  rounds_completed: number
  final_spread: number
  price_path: Array<{ round: number; role: string; price: number }>
  transcript: Array<Record<string, unknown>>
}

export interface BatchSimulationResult {
  batch_id: string
  status: string
  outcomes: ScenarioOutcome[]
  comparison: {
    win_rate: number
    deals_reached: number
    total_scenarios: number
    average_deal_price: number | null
    best_scenario: string | null
    best_price: number | null
  }
  created_at: string
}
