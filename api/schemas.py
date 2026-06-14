"""Pydantic request/response schemas for all API endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


# ── User schemas ──

class UserCreate(BaseModel):
    name: str
    email: str
    role: str = "buyer"
    budget_min: float | None = None
    budget_max: float | None = None
    life_stage: str | None = None
    investment_goals: dict = Field(default_factory=dict)
    risk_tolerance: str = "moderate"
    timeline_days: int = 90
    latitude: float | None = None
    longitude: float | None = None
    zip_code: str | None = None
    search_radius: int = 10
    preferred_types: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    life_stage: str | None = None
    investment_goals: dict | None = None
    risk_tolerance: str | None = None
    timeline_days: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    zip_code: str | None = None
    search_radius: int | None = None
    preferred_types: list[str] | None = None


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    budget_min: float | None = None
    budget_max: float | None = None
    life_stage: str | None = None
    investment_goals: dict = Field(default_factory=dict)
    risk_tolerance: str | None = None
    timeline_days: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    zip_code: str | None = None
    search_radius: int | None = None
    preferred_types: list[str] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Property schemas ──

class PropertyCreate(BaseModel):
    seller_id: str | None = None
    address: str
    latitude: float | None = None
    longitude: float | None = None
    asking_price: float
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None
    property_type: str | None = None
    hoa_fees: float = 0
    disclosures: dict = Field(default_factory=dict)
    neighborhood_data: dict = Field(default_factory=dict)


class PropertyUpdate(BaseModel):
    asking_price: float | None = None
    status: str | None = None
    disclosures: dict | None = None
    neighborhood_data: dict | None = None


class PropertyResponse(BaseModel):
    id: str
    seller_id: str | None = None
    address: str
    latitude: float | None = None
    longitude: float | None = None
    asking_price: float
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None
    property_type: str | None = None
    hoa_fees: float | None = None
    disclosures: dict = Field(default_factory=dict)
    neighborhood_data: dict = Field(default_factory=dict)
    status: str | None = None
    listed_at: datetime | None = None

    model_config = {"from_attributes": True}


class PropertyListResponse(BaseModel):
    properties: list[PropertyResponse]
    count: int


# ── Offer schemas ──

class OfferCreate(BaseModel):
    property_id: str
    buyer_id: str
    negotiation_id: str | None = None
    actor_role: Literal["buyer", "seller", "broker"] | None = "buyer"
    actor_user_id: str | None = None
    offer_price: float
    contingencies: list[str] = Field(default_factory=list)
    parent_offer_id: str | None = None
    message: str | None = Field(default=None, max_length=500)


class OfferResponse(BaseModel):
    id: str
    negotiation_id: str | None = None
    property_id: str
    buyer_id: str | None = None
    actor_role: str | None = None
    actor_user_id: str | None = None
    offer_price: float
    contingencies: list = Field(default_factory=list)
    status: str
    parent_offer_id: str | None = None
    message: str | None = None
    correlation_id: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Negotiation schemas ──

class NegotiationCreate(BaseModel):
    property_id: str
    buyer_id: str
    seller_id: str


class NegotiationResponse(BaseModel):
    id: str
    property_id: str
    buyer_id: str
    seller_id: str
    status: str
    round_count: int
    final_price: float | None = None
    correlation_id: str | None = None
    deadline_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class NegotiationOfferRequest(BaseModel):
    offer_price: float = Field(gt=0)
    from_role: Literal["buyer", "seller"]
    message: str = Field(default="", max_length=500)
    correlation_id: str | None = None


class NegotiationAcceptRequest(BaseModel):
    from_role: Literal["buyer", "seller"]
    final_price: float = Field(gt=0)
    correlation_id: str | None = None


class NegotiationTransitionRequest(BaseModel):
    action: Literal[
        "generate_contract",
        "schedule_inspection",
        "clear",
        "funds_transferred",
        "reject",
        "withdraw",
    ]
    from_role: Literal["buyer", "seller", "broker"] = "broker"
    message: str = Field(default="", max_length=500)
    correlation_id: str | None = None


class NegotiationAnalysisResponse(BaseModel):
    status: str | None = None
    round: int | None = None
    spread_percent: float | None = None
    offer_history: list[float] = Field(default_factory=list)
    zopa_detected: bool | None = None
    suggested_price: float | None = None
    recommendation: str | None = None
    broker_mediation_recommended: bool | None = None

    model_config = {"extra": "allow"}


class NegotiationOfferHistoryResponse(BaseModel):
    id: str
    property_id: str
    buyer_id: str | None = None
    offer_price: float
    actor_role: str | None = None
    actor_user_id: str | None = None
    status: str | None = None
    parent_offer_id: str | None = None
    correlation_id: str | None = None
    message: str | None = None
    created_at: datetime | None = None


class NegotiationEventResponse(BaseModel):
    event_type: str
    payload: dict = Field(default_factory=dict)
    sequence: int
    actor_type: str | None = None
    actor_id: str | None = None
    created_at: datetime | None = None


class NegotiationSessionResponse(BaseModel):
    id: str
    property_id: str
    buyer_id: str
    seller_id: str
    status: str
    round_count: int
    final_price: float | None = None
    deadline_at: datetime | None = None
    offer_history: list[NegotiationOfferHistoryResponse] = Field(default_factory=list)
    current_analysis: NegotiationAnalysisResponse = Field(
        default_factory=NegotiationAnalysisResponse
    )
    events: list[NegotiationEventResponse] = Field(default_factory=list)


class NegotiationMutationResponse(BaseModel):
    negotiation_id: str
    action: str
    old_status: str | None = None
    new_status: str
    round_count: int
    offer_price: float | None = None
    final_price: float | None = None
    deadline_at: datetime | None = None
    analysis: NegotiationAnalysisResponse | None = None


class NegotiationEventsResponse(BaseModel):
    negotiation_id: str
    events: list[NegotiationEventResponse] = Field(default_factory=list)


# ── Report schemas ──

class ReportRequest(BaseModel):
    user_id: str
    question: str = "What is the best investment strategy for this buyer?"
    ticks: int = 30
    # Optional location overrides from search page
    zip_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    property_type: str | None = None


class ReportStatusResponse(BaseModel):
    id: str
    user_id: str
    status: str
    progress: int = 0
    current_step: str = ""
    step_key: str = ""
    created_at: datetime | None = None
    error_message: str | None = None


class ReportResponse(BaseModel):
    id: str
    user_id: str
    seed_hash: str | None = None
    report_json: dict = Field(default_factory=dict)
    status: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Negotiation Simulation schemas ──

class NegotiationSimRequest(BaseModel):
    property_id: str
    buyer_user_id: str
    seller_user_id: str
    initial_offer: float
    asking_price: float
    seller_minimum: float
    buyer_maximum: float
    strategy: str = "balanced"  # aggressive, balanced, conservative
    max_rounds: int = 10
    report_id: str | None = None  # Optional MiroFish report for data-driven agents


class NegotiationSimStatusResponse(BaseModel):
    id: str
    status: str  # pending, running, completed, failed
    current_round: int = 0
    max_rounds: int = 10
    progress: int = 0
    transcript: list[dict] = Field(default_factory=list)
    created_at: datetime | None = None


class NegotiationSimResultResponse(BaseModel):
    id: str
    status: str
    outcome: str  # accepted, rejected, max_rounds, broker_stopped
    final_price: float | None = None
    rounds_completed: int = 0
    transcript: list[dict] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    created_at: datetime | None = None


# ── Saved Simulation Result schemas ──

class SimulationResultResponse(BaseModel):
    id: str
    user_id: str
    property_id: str
    batch_id: str | None = None
    scenario_name: str | None = None
    outcome: str
    final_price: float | None = None
    asking_price: float
    initial_offer: float
    rounds_completed: int = 0
    max_rounds: int = 10
    strategy: str = "balanced"
    summary: dict = Field(default_factory=dict)
    price_path: list = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SimulationResultListResponse(BaseModel):
    results: list[SimulationResultResponse]
    count: int


# ── Event schemas ──

# ── Household schemas ──

class HouseholdResponse(BaseModel):
    id: str
    name: str
    zip_code: str
    income_band: str
    household_size: int = 2
    num_children: int = 0
    primary_language: str = "english"
    age_bracket: str = "30-45"
    housing_type: str = "renter"
    has_housing_voucher: int = 0
    monthly_housing_cost: float = 0
    monthly_income: float = 0
    eviction_risk: float = 0.0
    housing_market_sentiment: float = 0.0
    policy_support_score: float = 0.0
    neighborhood_satisfaction: float = 0.5
    influence_weight: float = 0.5
    communication_style: str = "passive"
    social_connections: int = 0
    opinion_stability: float = 0.5
    persona_data: dict = Field(default_factory=dict)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class HouseholdListResponse(BaseModel):
    households: list[HouseholdResponse]
    count: int


# ── Social Simulation schemas ──

class SocialSimStartRequest(BaseModel):
    user_id: str
    zip_code: str | None = None
    income_band: str | None = None
    max_rounds: int = 10
    topics: list[str] = Field(
        default_factory=lambda: ["market_prices", "eviction_policy", "voucher_program", "neighborhood_safety"]
    )


class SocialSimStatusResponse(BaseModel):
    id: str
    status: str
    current_round: int = 0
    total_rounds: int = 10
    action_count: int = 0
    created_at: datetime | None = None
    error_message: str | None = None


class SocialSimActionResponse(BaseModel):
    id: str
    round_num: int
    household_id: str
    action_type: str
    topic: str
    content: str | None = None
    sentiment_value: float | None = None
    influenced_by: list[str] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SocialSimResultResponse(BaseModel):
    id: str
    status: str
    total_rounds: int
    current_round: int
    narrative_output: dict = Field(default_factory=dict)
    sentiment_delta: dict = Field(default_factory=dict)
    report_id: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class SocialSimTimelineEntry(BaseModel):
    round_num: int
    topic: str
    avg_sentiment: float
    action_count: int
    dominant_stance: str


class SocialSimTimelineResponse(BaseModel):
    run_id: str
    timeline: list[SocialSimTimelineEntry]


class SocialSimGenerateReportRequest(BaseModel):
    property_id: str
    household_id: str


# ── Visualization & Replay schemas ──

class MapOverlay(BaseModel):
    overlay_type: str  # "sentiment_zone", "risk_zone", "comparable", "household_cluster"
    center_lat: float
    center_lng: float
    radius_meters: float = 500
    value: float = 0.0
    label: str = ""
    color: str | None = None
    metadata: dict = Field(default_factory=dict)


class PropertyVisualizationResponse(BaseModel):
    property_id: str
    address: str
    latitude: float
    longitude: float
    asking_price: float
    property_type: str | None = None
    overlays: list[MapOverlay] = Field(default_factory=list)
    comparable_properties: list[PropertyResponse] = Field(default_factory=list)
    simulation_ids: list[str] = Field(default_factory=list)


class ConversationEvent(BaseModel):
    round_number: int
    timestamp: str
    role: str  # "system", "buyer", "seller", "broker"
    event_type: str  # "message", "offer", "counter_offer", "acceptance", "rejection", "broker_intervention"
    content: str
    numerical_state: dict = Field(default_factory=dict)
    tool_calls: list[dict] = Field(default_factory=list)


class SimulationReplayResponse(BaseModel):
    simulation_id: str
    batch_id: str | None = None
    scenario_name: str | None = None
    property_id: str
    asking_price: float
    initial_offer: float
    max_rounds: int
    events: list[ConversationEvent] = Field(default_factory=list)
    final_outcome: dict = Field(default_factory=dict)
    available_scenarios: list[str] = Field(default_factory=list)


class SimulationReplayListResponse(BaseModel):
    replays: list[SimulationReplayResponse]
    count: int


# ── Event schemas ──

class DomainEventResponse(BaseModel):
    id: str
    correlation_id: str | None = None
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict = Field(default_factory=dict)
    actor_type: str | None = None
    actor_id: str | None = None
    sequence: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MarketSimulationScope(BaseModel):
    property_ids: list[str] = Field(default_factory=list)
    zip_codes: list[str] = Field(default_factory=list)
    property_types: list[str] = Field(default_factory=list)
    min_price: float | None = None
    max_price: float | None = None
    include_pending: bool = False


class MarketInvestorPersona(BaseModel):
    display_name: str
    archetype: str
    budget: float
    risk_posture: str
    hold_horizon: str
    target_yield: str
    preferred_property_types: list[str] = Field(default_factory=list)
    preferred_price_band: str
    neighborhood_preferences: list[str] = Field(default_factory=list)
    avoidance_triggers: list[str] = Field(default_factory=list)
    competition_style: str
    exit_style: str
    investment_thesis: str


class MarketSimulationPersonaRequest(BaseModel):
    investor_count: int = Field(default=12, ge=1, le=100)
    cohort_preset: str = "balanced"
    scope: MarketSimulationScope = Field(default_factory=MarketSimulationScope)


class MarketSimulationPersonaResponse(BaseModel):
    property_count: int
    personas: list[MarketInvestorPersona] = Field(default_factory=list)
    inventory_summary: dict = Field(default_factory=dict)


class MarketSimulationStartRequest(BaseModel):
    investor_count: int = Field(default=12, ge=1, le=100)
    tick_count: int = Field(default=8, ge=1, le=50)
    cohort_preset: str = "balanced"
    run_label: str | None = None
    scope: MarketSimulationScope = Field(default_factory=MarketSimulationScope)
    seeded_personas: list[MarketInvestorPersona] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_seeded_personas(self) -> "MarketSimulationStartRequest":
        if self.seeded_personas and len(self.seeded_personas) != self.investor_count:
            raise ValueError("seeded_personas must match investor_count exactly")
        return self


class MarketSimulationStartResponse(BaseModel):
    run_id: str
    status: str
    message: str


class MarketSimulationStatusResponse(BaseModel):
    run_id: str
    status: str
    current_tick: int = 0
    total_ticks: int = 0
    progress: int = 0
    investor_count: int = 0
    property_count: int = 0
    run_label: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class MarketSimulationInvestorOutcomeSummary(BaseModel):
    decisions_made: int = 0
    watch_actions: int = 0
    bid_actions: int = 0
    acquisitions: int = 0
    last_action: str | None = None
    last_property_id: str | None = None
    last_property_address: str | None = None


class MarketSimulationInvestorResponse(BaseModel):
    id: str
    investor_name: str
    archetype: str
    budget: float
    cash_remaining: float
    hold_horizon_ticks: int
    risk_appetite: float
    diversification_cap: int
    preferred_property_types: list[str] = Field(default_factory=list)
    signal_weights: dict = Field(default_factory=dict)
    holdings: list[str] = Field(default_factory=list)
    persona: MarketInvestorPersona | None = None
    outcome_summary: MarketSimulationInvestorOutcomeSummary = Field(default_factory=MarketSimulationInvestorOutcomeSummary)


class PropertyTickState(BaseModel):
    property_id: str
    address: str
    latitude: float | None = None
    longitude: float | None = None
    asking_price: float
    property_type: str | None = None
    tick_num: int
    status: str
    attention_count: int = 0
    bid_count: int = 0
    top_bid: float | None = None
    bid_velocity: float = 0.0
    local_competition: float = 0.0
    recent_attention: float = 0.0
    reservation_threshold: float
    winning_investor_id: str | None = None
    signal_snapshot: dict = Field(default_factory=dict)
    targeted_investor_ids: list[str] = Field(default_factory=list)


class InvestorDecisionTrace(BaseModel):
    investor_id: str
    investor_name: str
    archetype: str
    tick_num: int
    property_id: str | None = None
    property_address: str | None = None
    chosen_action: str
    bid_amount: float | None = None
    total_score: float | None = None
    signal_scores: dict = Field(default_factory=dict)
    persona_weights: dict = Field(default_factory=dict)
    peer_inputs: dict = Field(default_factory=dict)
    property_match_factors: list[str] = Field(default_factory=list)
    budget_position: dict = Field(default_factory=dict)
    persona_summary: dict = Field(default_factory=dict)
    chosen_action_reason: str = ""
    entry_or_exit_reason: str = ""
    rejected_alternatives: list[dict] = Field(default_factory=list)


class InvestorTickState(BaseModel):
    tick_number: int
    property_states: list[PropertyTickState] = Field(default_factory=list)
    decisions: list[InvestorDecisionTrace] = Field(default_factory=list)


class MarketSimulationReplayResponse(BaseModel):
    run_id: str
    status: str
    run_label: str | None = None
    total_ticks: int
    completed_ticks: int
    investors: list[MarketSimulationInvestorResponse] = Field(default_factory=list)
    ticks: list[InvestorTickState] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


class MarketSimulationAcquisition(BaseModel):
    property_id: str
    property_address: str
    winning_investor_id: str
    winning_investor_name: str
    acquired_tick: int
    winning_bid: float


class MarketSimulationResultResponse(BaseModel):
    run_id: str
    status: str
    total_ticks: int
    completed_ticks: int
    summary: dict = Field(default_factory=dict)
    acquisitions: list[MarketSimulationAcquisition] = Field(default_factory=list)
    investors: list[MarketSimulationInvestorResponse] = Field(default_factory=list)


class MarketSimulationHandoffRequest(BaseModel):
    run_id: str
    investor_id: str
    property_id: str
    max_rounds: int = Field(default=10, ge=1, le=25)


class MarketSimulationHandoffResponse(BaseModel):
    simulation_id: str
    status: str
    investor_id: str
    property_id: str
    seeded_config: dict = Field(default_factory=dict)
    message: str


# ── Investor Portfolio schemas (Phase P1) ─────────────────────────────


class HoldingFinancialsCreate(BaseModel):
    cost_basis: float | None = None
    current_value_estimate: float | None = None
    value_estimate_source: str | None = None
    loan_balance: float | None = None
    interest_rate: float | None = None
    monthly_piti: float | None = None
    monthly_rent: float | None = None
    vacancy_rate: float | None = 0.05
    monthly_opex_estimate: float | None = None
    property_tax_annual: float | None = None
    insurance_annual: float | None = None


class HoldingFinancialsResponse(HoldingFinancialsCreate):
    id: str
    holding_id: str
    last_updated: datetime | None = None

    model_config = {"from_attributes": True}


class PortfolioHoldingCreate(BaseModel):
    address: str
    asset_class: str = "sfr"
    status: str = "held"
    property_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    zip_code: str | None = None
    acquisition_date: datetime | None = None
    financials: HoldingFinancialsCreate | None = None


class PortfolioHoldingResponse(BaseModel):
    id: str
    portfolio_id: str
    property_id: str | None = None
    address: str
    latitude: float | None = None
    longitude: float | None = None
    zip_code: str | None = None
    asset_class: str
    status: str
    acquisition_date: datetime | None = None
    financials: HoldingFinancialsResponse | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class InvestorPortfolioCreate(BaseModel):
    user_id: str
    name: str
    investment_strategy: str = "buy_hold"
    notes: str | None = None


class CsvImportRequest(BaseModel):
    """Bulk portfolio + holdings import payload for the onboarding wizard."""

    user_id: str
    user_email: str | None = None
    user_name: str | None = None
    portfolio_name: str = "My Portfolio"
    investment_strategy: str = "buy_hold"
    holdings: list[PortfolioHoldingCreate]


class CsvImportResponse(BaseModel):
    portfolio_id: str
    inserted_count: int
    updated_count: int
    skipped: list[str] = []


class PortfolioFromPropertyRequest(BaseModel):
    """Bridge for the no-portfolio onboarding path.

    Synthesizes a single-holding portfolio rooted at an existing ``Property``
    so the strategy runner has something to simulate against.
    """

    user_id: str
    user_email: str | None = None
    user_name: str | None = None
    property_id: str
    portfolio_name: str = "Recommended Property"
    investment_strategy: str = "buy_hold"


class ChatMessage(BaseModel):
    """One turn in the chat extraction conversation."""

    role: str  # "user" | "assistant"
    content: str


class ChatImportRequest(BaseModel):
    """Free-text conversation that should yield structured holdings."""

    messages: list[ChatMessage]


class ChatImportResponse(BaseModel):
    """Extraction result — caller must POST to /confirm to commit."""

    narration: str
    holdings: list[PortfolioHoldingCreate]


class ChatImportConfirm(BaseModel):
    """Final list of holdings the user approved — commits via CSV path."""

    user_id: str
    user_email: str | None = None
    user_name: str | None = None
    portfolio_name: str = "My Portfolio"
    investment_strategy: str = "buy_hold"
    holdings: list[PortfolioHoldingCreate]


class InvestorProfileGeography(BaseModel):
    """One-of constraint: at least one of zip/city/state must be set."""

    zip: str | None = None
    city: str | None = None
    state: str | None = None


class InvestorProfileUpsert(BaseModel):
    """Wizard-side input — fields that aren't provided default to None."""

    user_id: str
    user_email: str | None = None
    user_name: str | None = None
    budget: float | None = None
    strategy: str | None = None  # buy_and_hold | flip | lease
    target_cap_rate: float | None = None  # %
    target_coc: float | None = None  # %
    geography: InvestorProfileGeography = InvestorProfileGeography()
    notes: str | None = None


class InvestorProfileResponse(BaseModel):
    id: str
    user_id: str
    budget: float | None = None
    strategy: str | None = None
    target_cap_rate: float | None = None
    target_coc: float | None = None
    geography: InvestorProfileGeography
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PropertyRecommendation(BaseModel):
    """One ranked property card returned to the wizard."""

    property_id: str
    address: str
    asking_price: float
    property_type: str | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None
    score: float
    rationale: list[str]


class PropertyRecommendationsResponse(BaseModel):
    recommendations: list[PropertyRecommendation]
    profile_id: str | None = None
    candidates_considered: int


class InvestorPortfolioResponse(BaseModel):
    id: str
    user_id: str
    name: str
    investment_strategy: str
    notes: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Underwriting + listing schemas (Phase P2) ─────────────────────────


class UnderwriteRequest(BaseModel):
    purchase_price: float = Field(gt=0)
    down_payment: float = Field(ge=0)
    loan_rate: float = Field(default=0.07, ge=0, le=0.5)
    loan_term_years: int = Field(default=30, ge=1, le=50)
    monthly_rent: float = Field(default=0, ge=0)
    vacancy_rate: float = Field(default=0.05, ge=0, le=1)
    monthly_opex: float = Field(default=0, ge=0)
    property_tax_annual: float = Field(default=0, ge=0)
    insurance_annual: float = Field(default=0, ge=0)
    closing_costs: float = Field(default=0, ge=0)
    rent_growth: float = Field(default=0.03, ge=-0.5, le=0.5)
    expense_growth: float = Field(default=0.025, ge=-0.5, le=0.5)
    appreciation: float = Field(default=0.03, ge=-0.5, le=0.5)
    exit_cap_rate: float = Field(default=0.07, gt=0, le=0.5)
    selling_costs_pct: float = Field(default=0.06, ge=0, le=0.2)


class UnderwriteResponse(BaseModel):
    monthly_piti: float
    annual_debt_service: float
    effective_gross_income: float
    annual_noi: float
    cap_rate: float
    cash_on_cash: float
    dscr: float
    breakeven_occupancy: float
    initial_equity: float
    irr_5yr: float | None = None
    irr_10yr: float | None = None


class SliderRangeSchema(BaseModel):
    low: float
    high: float


class StressTestConfigSchema(BaseModel):
    iterations: int = Field(default=5000, ge=10, le=20000)
    seed: int | None = None
    vacancy_rate: SliderRangeSchema = SliderRangeSchema(low=0.03, high=0.12)
    rent_growth: SliderRangeSchema = SliderRangeSchema(low=0.0, high=0.04)
    expense_growth: SliderRangeSchema = SliderRangeSchema(low=0.02, high=0.04)
    loan_rate: SliderRangeSchema = SliderRangeSchema(low=0.05, high=0.08)
    exit_cap_rate: SliderRangeSchema = SliderRangeSchema(low=0.06, high=0.085)


class StressTestRequest(BaseModel):
    base_inputs: UnderwriteRequest
    config: StressTestConfigSchema = Field(default_factory=StressTestConfigSchema)


class StressTestResponse(BaseModel):
    iterations: int
    cap_rate_p10: float
    cap_rate_p50: float
    cap_rate_p90: float
    cash_on_cash_p10: float
    cash_on_cash_p50: float
    cash_on_cash_p90: float
    dscr_p10: float
    dscr_p50: float
    dscr_p90: float
    irr_5yr_p10: float | None = None
    irr_5yr_p50: float | None = None
    irr_5yr_p90: float | None = None
    probability_negative_cash_flow: float
    probability_dscr_under_1: float
    tornado: dict


class ListingParseRequest(BaseModel):
    url: str


class ListingParseResponse(BaseModel):
    source: str
    property_id: str
    url: str
    address_hint: str
    prefecture: str | None = None
    postal_code: str | None = None


class PortfolioAggregateResponse(BaseModel):
    portfolio_id: str
    holding_count: int
    total_value: float
    total_loan_balance: float
    total_equity: float
    total_cost_basis: float
    monthly_gross_rent: float
    monthly_net_operating_income: float
    monthly_cash_flow: float
    blended_cap_rate: float
    weighted_dscr: float | None = None
    concentration: dict  # by zip / asset_class
    asset_class_mix: dict
    investment_strategy: str


# ── Phase P4 — holding decision recommendations ─────────────────────────


class DecisionCandidate(BaseModel):
    """One scored investor action considered for a holding."""

    action: str  # HOLD | RAISE_RENT | REFI | SELL | IMPROVE
    score: float
    rationale: str
    source: str  # decision policy kind or "financial_heuristic"


class HoldingDecisionResponse(BaseModel):
    holding_id: str
    recommendation: str  # top-ranked action label
    score: float
    rationale: str
    market_context_available: bool
    candidates: list[DecisionCandidate]


# ── Phase S2 — portfolio summary report ────────────────────────────────


class HoldingSummaryEntry(BaseModel):
    """One holding's per-deal analysis row inside the summary."""

    holding_id: str
    address: str
    zip_code: str | None = None
    asset_class: str
    current_value: float | None = None
    monthly_cash_flow: float | None = None
    cap_rate: float | None = None
    dscr: float | None = None
    cash_on_cash: float | None = None
    recommendation: str
    recommendation_score: float
    recommendation_rationale: str
    market_context_available: bool
    # JP depreciation inputs (Phase 4) — null when the holding is off-platform
    # or the linked Property/HoldingFinancials lacks the required fields.
    construction_type: str | None = None
    building_age_years: int | None = None
    building_basis_yen: float | None = None


class PortfolioAttentionItem(BaseModel):
    """One holding flagged for non-HOLD action — surfaces at the top of the UI."""

    holding_id: str
    address: str
    action: str
    score: float
    rationale: str


class MarketCoverage(BaseModel):
    total: int
    with_signals: int


class PortfolioSummaryAggregates(BaseModel):
    total_value: float
    total_loan_balance: float
    total_equity: float
    monthly_gross_rent: float
    monthly_net_operating_income: float
    monthly_cash_flow: float
    annual_noi: float
    blended_cap_rate: float
    weighted_dscr: float | None = None


class PortfolioSummaryReport(BaseModel):
    portfolio_id: str
    generated_at: datetime
    holding_count: int
    aggregates: PortfolioSummaryAggregates
    per_holding: list[HoldingSummaryEntry]
    attention: list[PortfolioAttentionItem]
    market_coverage: MarketCoverage


# ── Phase S5 — strategy profile (free-text → structured) ───────────────


class StrategyAssumptions(BaseModel):
    """User assumptions about market behavior. Feed underwrite + Monte Carlo."""

    rent_growth: float = Field(default=0.03, ge=-0.5, le=0.5)
    expense_growth: float = Field(default=0.025, ge=-0.5, le=0.5)
    vacancy_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    hold_period_years: int = Field(default=10, ge=1, le=50)
    exit_cap_rate: float = Field(default=0.07, gt=0.0, le=0.5)
    loan_rate_outlook: float | None = None
    # JP investor marginal income-tax bracket — drives depreciation tax shield value.
    marginal_tax_rate: float = Field(default=0.33, ge=0.0, le=1.0)


class StrategyPolicyConfig(BaseModel):
    """User preferences that steer DecisionRuntime + financial heuristics."""

    risk_tolerance: str = Field(default="medium")  # low | medium | high
    refi_rate_threshold: float = Field(default=0.06, ge=0.0, le=0.5)
    sell_bias: float = Field(default=0.0, ge=-1.0, le=1.0)
    raise_rent_bias: float = Field(default=0.0, ge=-1.0, le=1.0)
    tenant_protection: bool = False


class StrategyThesis(BaseModel):
    """User outlook on the neighborhoods and the market story."""

    trajectory: str = Field(default="none")  # neighborhood_trajectory | displacement_pressure | none
    market_outlook: str = Field(default="neutral")  # bullish | neutral | bearish
    sentiment_topics: list[str] = Field(default_factory=list)
    notes: str | None = None


class StrategyProfile(BaseModel):
    """Structured form of the user's current investing strategy or opinion."""

    assumptions: StrategyAssumptions = Field(default_factory=StrategyAssumptions)
    policy_config: StrategyPolicyConfig = Field(default_factory=StrategyPolicyConfig)
    thesis: StrategyThesis = Field(default_factory=StrategyThesis)


class StrategyInput(BaseModel):
    """User-supplied free text describing their strategy or opinion."""

    portfolio_id: str
    text: str = ""


class StrategyExtractResponse(BaseModel):
    """LLM-seeded profile sent back for review/override."""

    profile: StrategyProfile


# ── Phase S6/S7 — strategy run pipeline ────────────────────────────────


class HoldingProjection(BaseModel):
    holding_id: str
    address: str
    horizon_years: int
    projected_value: float | None = None
    projected_annual_noi: float | None = None
    projected_cap_rate: float | None = None
    projected_monthly_cash_flow: float | None = None
    projected_recommendation: str
    # Depreciation tax shield (Phase 4) — populated when construction info exists.
    annual_tax_shield_yen: float | None = None
    total_tax_shield_yen: float | None = None
    shield_expires_year: int | None = None
    shield_expired_in_horizon: bool = False


class SimulationReport(BaseModel):
    portfolio_id: str
    horizon_years: int
    per_holding: list[HoldingProjection]
    aggregate_value_projection: float
    aggregate_annual_noi_projection: float
    aggregate_cap_rate_projection: float | None = None
    notes: list[str] = Field(default_factory=list)


class HoldingReconciliation(BaseModel):
    """How a single holding's recommendation changes under projection."""

    holding_id: str
    address: str
    today_action: str
    projected_action: str
    flipped: bool
    note: str | None = None


class UnifiedReport(BaseModel):
    portfolio_id: str
    horizon_years: int
    survives: bool
    confidence: float
    agreements: list[str]
    divergences: list[str]
    reconciliations: list[HoldingReconciliation]
    summary: str


class StrategyRunRequest(BaseModel):
    portfolio_id: str
    text: str = ""
    profile: StrategyProfile | None = None  # optional override after review


class StrategyRunStartResponse(BaseModel):
    run_id: str
    portfolio_id: str
    status: str
    profile: StrategyProfile


class StrategyRunStep(BaseModel):
    """One incremental event in a strategy run.

    Emitted by the runner and forwarded over WebSocket + persisted on the
    final ``StrategyRunRecord`` so HTTP-only clients can recover the trace.
    """

    type: str  # e.g. "run.started", "step.analysis_built"
    label: str  # human-readable name shown in the timeline
    detail: str | None = None
    at: datetime


class StrategyRunRecord(BaseModel):
    run_id: str
    portfolio_id: str
    status: str  # pending | running | completed | failed
    profile: StrategyProfile
    analysis: PortfolioSummaryReport | None = None
    simulation: SimulationReport | None = None
    unified: UnifiedReport | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    steps: list[StrategyRunStep] = []


# ── Public runtime config ──────────────────────────────────────────────


class PublicRuntimeConfigResponse(BaseModel):
    """Browser-safe runtime settings (env, API base, Supabase, map style)."""

    environment: str
    api_base_url: str
    ws_base_url: str
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    map_style_url: str = ""


# ── Phase 3A — Persona analyst council ────────────────────────────────


class AnalystVerdictSchema(BaseModel):
    persona_key: str
    persona_title_ja: str
    payload: dict
    error: str | None = None


class ListingAnalysisResponse(BaseModel):
    listing_id: str
    overall_score: float
    summary: str
    verdicts: list[AnalystVerdictSchema]


class ListingAnalysisRequest(BaseModel):
    """Investor-side overrides for the depreciation strategist."""

    building_basis_yen: float | None = None
    building_age_years: int | None = None
    marginal_tax_rate: float = Field(0.33, ge=0, le=1)

