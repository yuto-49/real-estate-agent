"""Pydantic request/response schemas for all API endpoints."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


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
    offer_price: float
    contingencies: list[str] = Field(default_factory=list)
    parent_offer_id: str | None = None


class OfferResponse(BaseModel):
    id: str
    property_id: str
    buyer_id: str
    offer_price: float
    contingencies: list = Field(default_factory=list)
    status: str
    parent_offer_id: str | None = None
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
