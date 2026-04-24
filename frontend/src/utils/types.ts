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

export type NegotiationRole = 'buyer' | 'seller' | 'broker'
export type NegotiationTransitionAction =
  | 'generate_contract'
  | 'schedule_inspection'
  | 'clear'
  | 'funds_transferred'
  | 'reject'
  | 'withdraw'

export interface NegotiationAnalysis {
  status?: string | null
  round?: number | null
  spread_percent?: number | null
  offer_history: number[]
  zopa_detected?: boolean | null
  suggested_price?: number | null
  recommendation?: string | null
  broker_mediation_recommended?: boolean | null
  [key: string]: unknown
}

export interface NegotiationOfferHistoryEntry {
  id: string
  property_id: string
  buyer_id?: string | null
  offer_price: number
  actor_role?: string | null
  actor_user_id?: string | null
  status?: string | null
  parent_offer_id?: string | null
  correlation_id?: string | null
  message?: string | null
  created_at?: string | null
}

export interface NegotiationEventReplayEntry {
  event_type: string
  payload: Record<string, unknown>
  sequence: number
  actor_type?: string | null
  actor_id?: string | null
  created_at?: string | null
}

export interface NegotiationSession extends Negotiation {
  offer_history: NegotiationOfferHistoryEntry[]
  current_analysis: NegotiationAnalysis
  events: NegotiationEventReplayEntry[]
}

export interface NegotiationOfferRequest {
  offer_price: number
  from_role: 'buyer' | 'seller'
  message?: string
  correlation_id?: string | null
}

export interface NegotiationAcceptRequest {
  from_role: 'buyer' | 'seller'
  final_price: number
  correlation_id?: string | null
}

export interface NegotiationTransitionRequest {
  action: NegotiationTransitionAction
  from_role?: NegotiationRole
  message?: string
  correlation_id?: string | null
}

export interface NegotiationMutationResponse {
  negotiation_id: string
  action: string
  old_status?: string | null
  new_status: string
  round_count: number
  offer_price?: number | null
  final_price?: number | null
  deadline_at?: string | null
  analysis?: NegotiationAnalysis | null
}

export type SocialSimTopic =
  | 'market_prices'
  | 'eviction_policy'
  | 'voucher_program'
  | 'neighborhood_safety'

export interface SocialSimStartRequest {
  user_id: string
  zip_code?: string
  income_band?: string
  max_rounds?: number
  topics?: SocialSimTopic[]
}

export interface SocialSimStartResponse {
  run_id: string
  status: string
  message: string
}

export interface SocialSimStatus {
  id: string
  status: string
  current_round: number
  total_rounds: number
  action_count: number
  created_at?: string | null
  error_message?: string | null
}

export interface SocialSimAction {
  id: string
  round_num: number
  household_id: string
  action_type: string
  topic: string
  content?: string | null
  sentiment_value?: number | null
  influenced_by: string[]
  created_at?: string | null
}

export interface SocialSimTimelineEntry {
  round_num: number
  topic: string
  avg_sentiment: number
  action_count: number
  dominant_stance: string
}

export interface SocialSimTimelineResponse {
  run_id: string
  timeline: SocialSimTimelineEntry[]
}

export interface SocialSimResult {
  id: string
  status: string
  total_rounds: number
  current_round: number
  narrative_output: Record<string, unknown>
  sentiment_delta: Record<string, unknown>
  report_id?: string | null
  created_at?: string | null
  completed_at?: string | null
  error_message?: string | null
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

// ── Visualization & Replay Types ──

export interface MapOverlay {
  overlay_type: string
  center_lat: number
  center_lng: number
  radius_meters: number
  value: number
  label: string
  color: string | null
  metadata: Record<string, unknown>
}

export interface PropertyVisualization {
  property_id: string
  address: string
  latitude: number
  longitude: number
  asking_price: number
  property_type: string | null
  overlays: MapOverlay[]
  comparable_properties: Property[]
  simulation_ids: string[]
}

export interface ConversationEvent {
  round_number: number
  timestamp: string
  role: 'system' | 'buyer' | 'seller' | 'broker'
  event_type: string
  content: string
  numerical_state: {
    buyer_offer?: number
    seller_ask?: number
    spread?: number
    status?: string
  }
  tool_calls: Array<Record<string, unknown>>
}

export interface SimulationReplay {
  simulation_id: string
  batch_id: string | null
  scenario_name: string | null
  property_id: string
  asking_price: number
  initial_offer: number
  max_rounds: number
  events: ConversationEvent[]
  final_outcome: {
    status: string
    final_price: number | null
    rounds_completed: number
    spread: number
    buyer_final: number
    seller_final: number
  }
  available_scenarios: string[]
}

export interface SimulationUIState {
  selectedPropertyId: string | null
  activeSimulationId: string | null
  activeScenario: string | null
  currentRoundIndex: number
  isPopupOpen: boolean
  isReplayPlaying: boolean
  mapCenter: { lat: number; lng: number } | null
  propertyVisualization: PropertyVisualization | null
  simulationReplay: SimulationReplay | null
}
