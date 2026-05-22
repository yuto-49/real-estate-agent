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

// ── Market Simulation Types ──

export interface MarketSimulationScope {
  property_ids: string[]
  zip_codes: string[]
  property_types: string[]
  min_price?: number | null
  max_price?: number | null
  include_pending: boolean
}

export interface MarketInvestorPersona {
  display_name: string
  archetype: string
  budget: number
  risk_posture: string
  hold_horizon: string
  target_yield: string
  preferred_property_types: string[]
  preferred_price_band: string
  neighborhood_preferences: string[]
  avoidance_triggers: string[]
  competition_style: string
  exit_style: string
  investment_thesis: string
}

export interface MarketSimulationPersonaResponse {
  property_count: number
  personas: MarketInvestorPersona[]
  inventory_summary: Record<string, unknown>
}

export interface MarketSimulationStartResponse {
  run_id: string
  status: string
  message: string
}

export interface MarketSimulationRunStatus {
  run_id: string
  status: string
  current_tick: number
  total_ticks: number
  progress: number
  investor_count: number
  property_count: number
  run_label?: string | null
  error_message?: string | null
  created_at?: string | null
  completed_at?: string | null
}

export interface MarketSimulationInvestorOutcomeSummary {
  decisions_made: number
  watch_actions: number
  bid_actions: number
  acquisitions: number
  last_action?: string | null
  last_property_id?: string | null
  last_property_address?: string | null
}

export interface MarketSimulationInvestor {
  id: string
  investor_name: string
  archetype: string
  budget: number
  cash_remaining: number
  hold_horizon_ticks: number
  risk_appetite: number
  diversification_cap: number
  preferred_property_types: string[]
  signal_weights: Record<string, number>
  holdings: string[]
  persona?: MarketInvestorPersona | null
  outcome_summary: MarketSimulationInvestorOutcomeSummary
}

export interface PropertyTickState {
  property_id: string
  address: string
  latitude?: number | null
  longitude?: number | null
  asking_price: number
  property_type?: string | null
  tick_num: number
  status: string
  attention_count: number
  bid_count: number
  top_bid?: number | null
  bid_velocity: number
  local_competition: number
  recent_attention: number
  reservation_threshold: number
  winning_investor_id?: string | null
  signal_snapshot: Record<string, number>
  targeted_investor_ids: string[]
}

export interface InvestorDecisionTrace {
  investor_id: string
  investor_name: string
  archetype: string
  tick_num: number
  property_id?: string | null
  property_address?: string | null
  chosen_action: 'watch' | 'enter' | 'raise_bid' | 'hold' | 'exit' | 'acquire' | 'skip'
  bid_amount?: number | null
  total_score?: number | null
  signal_scores: Record<string, number>
  persona_weights: Record<string, number>
  peer_inputs: Record<string, number>
  property_match_factors: string[]
  budget_position: Record<string, unknown>
  persona_summary: Record<string, unknown>
  chosen_action_reason: string
  entry_or_exit_reason: string
  rejected_alternatives: Array<Record<string, unknown>>
}

export interface MarketSimulationTick {
  tick_number: number
  property_states: PropertyTickState[]
  decisions: InvestorDecisionTrace[]
}

export interface MarketSimulationReplay {
  run_id: string
  status: string
  run_label?: string | null
  total_ticks: number
  completed_ticks: number
  investors: MarketSimulationInvestor[]
  ticks: MarketSimulationTick[]
  summary: Record<string, unknown>
}

export interface MarketSimulationAcquisition {
  property_id: string
  property_address: string
  winning_investor_id: string
  winning_investor_name: string
  acquired_tick: number
  winning_bid: number
}

export interface MarketSimulationRunResult {
  run_id: string
  status: string
  total_ticks: number
  completed_ticks: number
  summary: Record<string, unknown>
  acquisitions: MarketSimulationAcquisition[]
  investors: MarketSimulationInvestor[]
}

export interface MarketSimulationHandoffResponse {
  simulation_id: string
  status: string
  investor_id: string
  property_id: string
  seeded_config: Record<string, unknown>
  message: string
}

// ── Investor portfolio (Phase P6) ──────────────────────────────────────

export type PortfolioMode = 'institutional' | 'individual'

export interface HoldingFinancials {
  cost_basis?: number | null
  current_value_estimate?: number | null
  value_estimate_source?: string | null
  loan_balance?: number | null
  interest_rate?: number | null
  monthly_piti?: number | null
  monthly_rent?: number | null
  vacancy_rate?: number | null
  monthly_opex_estimate?: number | null
  property_tax_annual?: number | null
  insurance_annual?: number | null
}

export interface PortfolioHoldingCreate {
  address: string
  asset_class?: string
  status?: string
  property_id?: string | null
  latitude?: number | null
  longitude?: number | null
  zip_code?: string | null
  financials?: HoldingFinancials | null
}

export interface PortfolioHolding {
  id: string
  portfolio_id: string
  property_id?: string | null
  address: string
  zip_code?: string | null
  asset_class: string
  status: string
  financials?: (HoldingFinancials & { id: string; holding_id: string }) | null
  created_at?: string | null
}

export interface InvestorPortfolio {
  id: string
  user_id: string
  name: string
  investment_strategy: string
  notes?: string | null
  created_at?: string | null
}

export interface PortfolioAggregate {
  portfolio_id: string
  holding_count: number
  total_value: number
  total_loan_balance: number
  total_equity: number
  total_cost_basis: number
  monthly_gross_rent: number
  monthly_net_operating_income: number
  monthly_cash_flow: number
  blended_cap_rate: number
  weighted_dscr?: number | null
  concentration: Record<string, unknown>
  asset_class_mix: Record<string, number>
  investment_strategy: string
}

export interface UnderwriteRequest {
  purchase_price: number
  down_payment: number
  loan_rate?: number
  loan_term_years?: number
  monthly_rent?: number
  vacancy_rate?: number
  monthly_opex?: number
  property_tax_annual?: number
  insurance_annual?: number
  closing_costs?: number
  rent_growth?: number
  expense_growth?: number
  appreciation?: number
  exit_cap_rate?: number
  selling_costs_pct?: number
}

export interface UnderwriteResponse {
  monthly_piti: number
  annual_debt_service: number
  effective_gross_income: number
  annual_noi: number
  cap_rate: number
  cash_on_cash: number
  dscr: number
  breakeven_occupancy: number
  initial_equity: number
  irr_5yr?: number | null
  irr_10yr?: number | null
}

export interface SliderRange {
  low: number
  high: number
}

export interface StressTestConfig {
  iterations?: number
  seed?: number | null
  vacancy_rate?: SliderRange
  rent_growth?: SliderRange
  expense_growth?: SliderRange
  loan_rate?: SliderRange
  exit_cap_rate?: SliderRange
}

export interface StressTestResponse {
  iterations: number
  cap_rate_p10: number
  cap_rate_p50: number
  cap_rate_p90: number
  cash_on_cash_p10: number
  cash_on_cash_p50: number
  cash_on_cash_p90: number
  dscr_p10: number
  dscr_p50: number
  dscr_p90: number
  irr_5yr_p10?: number | null
  irr_5yr_p50?: number | null
  irr_5yr_p90?: number | null
  probability_negative_cash_flow: number
  probability_dscr_under_1: number
  tornado: Record<string, unknown>
}

export interface DecisionCandidate {
  action: string
  score: number
  rationale: string
  source: string
}

export interface HoldingDecisionResponse {
  holding_id: string
  recommendation: string
  score: number
  rationale: string
  market_context_available: boolean
  candidates: DecisionCandidate[]
}

// ── Phase S2/S3 — portfolio summary report ────────────────────────────

export interface HoldingSummaryEntry {
  holding_id: string
  address: string
  zip_code?: string | null
  asset_class: string
  current_value?: number | null
  monthly_cash_flow?: number | null
  cap_rate?: number | null
  dscr?: number | null
  cash_on_cash?: number | null
  recommendation: string
  recommendation_score: number
  recommendation_rationale: string
  market_context_available: boolean
}

export interface PortfolioAttentionItem {
  holding_id: string
  address: string
  action: string
  score: number
  rationale: string
}

export interface MarketCoverage {
  total: number
  with_signals: number
}

export interface PortfolioSummaryAggregates {
  total_value: number
  total_loan_balance: number
  total_equity: number
  monthly_gross_rent: number
  monthly_net_operating_income: number
  monthly_cash_flow: number
  annual_noi: number
  blended_cap_rate: number
  weighted_dscr?: number | null
}

export interface PortfolioSummaryReport {
  portfolio_id: string
  generated_at: string
  holding_count: number
  aggregates: PortfolioSummaryAggregates
  per_holding: HoldingSummaryEntry[]
  attention: PortfolioAttentionItem[]
  market_coverage: MarketCoverage
}

// ── Phase S5/S6/S7 — strategy runtime ────────────────────────────────

export interface StrategyAssumptions {
  rent_growth: number
  expense_growth: number
  vacancy_rate: number
  hold_period_years: number
  exit_cap_rate: number
  loan_rate_outlook?: number | null
}

export interface StrategyPolicyConfig {
  risk_tolerance: string
  refi_rate_threshold: number
  sell_bias: number
  raise_rent_bias: number
  tenant_protection: boolean
}

export interface StrategyThesis {
  trajectory: string
  market_outlook: string
  sentiment_topics: string[]
  notes?: string | null
}

export interface StrategyProfile {
  assumptions: StrategyAssumptions
  policy_config: StrategyPolicyConfig
  thesis: StrategyThesis
}

export interface StrategyExtractResponse {
  profile: StrategyProfile
}

export interface HoldingProjection {
  holding_id: string
  address: string
  horizon_years: number
  projected_value?: number | null
  projected_annual_noi?: number | null
  projected_cap_rate?: number | null
  projected_monthly_cash_flow?: number | null
  projected_recommendation: string
}

export interface SimulationReport {
  portfolio_id: string
  horizon_years: number
  per_holding: HoldingProjection[]
  aggregate_value_projection: number
  aggregate_annual_noi_projection: number
  aggregate_cap_rate_projection?: number | null
  notes: string[]
}

export interface HoldingReconciliation {
  holding_id: string
  address: string
  today_action: string
  projected_action: string
  flipped: boolean
  note?: string | null
}

export interface UnifiedReport {
  portfolio_id: string
  horizon_years: number
  survives: boolean
  confidence: number
  agreements: string[]
  divergences: string[]
  reconciliations: HoldingReconciliation[]
  summary: string
}

export interface StrategyRunStep {
  type: string
  label: string
  detail?: string | null
  at: string
}

export interface StrategyRunRecord {
  run_id: string
  portfolio_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  profile: StrategyProfile
  analysis?: PortfolioSummaryReport | null
  simulation?: SimulationReport | null
  unified?: UnifiedReport | null
  error?: string | null
  started_at: string
  completed_at?: string | null
  steps?: StrategyRunStep[]
}

export interface StrategyRunStartResponse {
  run_id: string
  portfolio_id: string
  status: string
  profile: StrategyProfile
}

export interface InvestorProfileGeography {
  zip?: string | null
  city?: string | null
  state?: string | null
}

export interface InvestorProfile {
  id: string
  user_id: string
  budget: number | null
  strategy: string | null
  target_cap_rate: number | null
  target_coc: number | null
  geography: InvestorProfileGeography
  notes?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface InvestorProfileUpsert {
  user_id: string
  user_email?: string | null
  user_name?: string | null
  budget?: number | null
  strategy?: string | null
  target_cap_rate?: number | null
  target_coc?: number | null
  geography?: InvestorProfileGeography
  notes?: string | null
}

export interface PropertyRecommendation {
  property_id: string
  address: string
  asking_price: number
  property_type?: string | null
  bedrooms?: number | null
  bathrooms?: number | null
  sqft?: number | null
  score: number
  rationale: string[]
}
