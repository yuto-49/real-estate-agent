"""SQLAlchemy models — maps directly to Section 8 of the spec."""

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column, String, Float, Integer, Numeric, Text, DateTime, ForeignKey, Enum, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.database import Base


def gen_uuid():
    return str(uuid4())


class LifeStage(str, enum.Enum):
    FIRST_TIME = "first_time"
    RELOCATING = "relocating"
    INVESTOR = "investor"
    DOWNSIZING = "downsizing"
    UPGRADING = "upgrading"


class RiskTolerance(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class NegotiationStatus(str, enum.Enum):
    IDLE = "idle"
    OFFER_PENDING = "offer_pending"
    COUNTER_PENDING = "counter_pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    ESCALATED = "escalated"
    CONTRACT_PHASE = "contract_phase"
    INSPECTION = "inspection"
    CLOSING = "closing"
    CLOSED = "closed"


class PropertyStatus(str, enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"


# ── Investor Portfolio enums (Phase P1) ───────────────────────────────


class PortfolioMode(str, enum.Enum):
    """Top-nav mode toggle — drives default landing route and nav surfacing."""

    INSTITUTIONAL = "institutional"
    INDIVIDUAL = "individual"


class InvestmentStrategy(str, enum.Enum):
    BUY_HOLD = "buy_hold"
    BRRRR = "brrrr"
    FIX_FLIP = "fix_flip"
    MIXED = "mixed"


class AssetClass(str, enum.Enum):
    SFR = "sfr"
    MF_2_4 = "mf_2_4"
    MF_5_PLUS = "mf_5_plus"
    CONDO = "condo"
    TOWNHOUSE = "townhouse"


class HoldingStatus(str, enum.Enum):
    HELD = "held"
    UNDER_REHAB = "under_rehab"
    LISTED = "listed"
    SOLD = "sold"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
    supabase_user_id = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    role = Column(String, default="buyer")  # buyer, seller, both
    budget_min = Column(Float)
    budget_max = Column(Float)
    life_stage = Column(Enum(LifeStage))
    investment_goals = Column(JSONB, default=dict)
    risk_tolerance = Column(Enum(RiskTolerance), default=RiskTolerance.MODERATE)
    timeline_days = Column(Integer, default=90)
    latitude = Column(Float)
    longitude = Column(Float)
    zip_code = Column(String)
    search_radius = Column(Integer, default=10)  # miles
    preferred_types = Column(JSONB, default=list)  # ["sfr", "condo", "multifamily"]
    preferred_mode = Column(
        Enum(
            PortfolioMode,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=PortfolioMode.INSTITUTIONAL,
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Property(Base):
    __tablename__ = "properties"

    id = Column(String, primary_key=True, default=gen_uuid)
    seller_id = Column(String, ForeignKey("user_profiles.id"))
    address = Column(String, nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    asking_price = Column(Float, nullable=False)
    bedrooms = Column(Integer)
    bathrooms = Column(Float)
    sqft = Column(Integer)
    property_type = Column(String)  # sfr, condo, duplex, triplex
    hoa_fees = Column(Float, default=0)
    disclosures = Column(JSONB, default=dict)
    neighborhood_data = Column(JSONB, default=dict)
    status = Column(Enum(PropertyStatus), default=PropertyStatus.ACTIVE)
    listed_at = Column(DateTime, default=datetime.utcnow)

    # --- JP additive columns (Phase 1 of Tokyo release) -------------------
    # All nullable — US records created before the migration keep working.
    address_jp = Column(JSONB, nullable=True)
    nearest_stations = Column(JSONB, nullable=True, default=list)
    built_year = Column(Integer, nullable=True)
    structure = Column(String(32), nullable=True)
    youto_chiiki = Column(String(64), nullable=True)
    kenpei_ritsu = Column(Integer, nullable=True)
    youseki_ritsu = Column(Integer, nullable=True)
    menseki_m2 = Column(Float, nullable=True)
    baibai_kakaku_yen = Column(Numeric(15, 0), nullable=True)
    kanrihi_yen = Column(Integer, nullable=True)
    shuuzenzumitatekin_yen = Column(Integer, nullable=True)
    takken_bukken_bangou = Column(String(64), nullable=True, unique=False, index=True)
    hazard_flags = Column(JSONB, nullable=True, default=dict)
    currency = Column(String(3), nullable=True, default="JPY")
    jurisdiction = Column(String(16), nullable=True, default="us", index=True)


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        Index("ix_offers_actor_user_id", "actor_user_id"),
        Index("ix_offers_parent_offer_id", "parent_offer_id"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    negotiation_id = Column(String, ForeignKey("negotiations.id"), nullable=True, index=True)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    buyer_id = Column(String, ForeignKey("user_profiles.id"), nullable=True)
    actor_role = Column(String, nullable=True)  # buyer, seller, broker
    actor_user_id = Column(String, ForeignKey("user_profiles.id"), nullable=True)
    offer_price = Column(Float, nullable=False)
    contingencies = Column(JSONB, default=list)
    status = Column(String, default="pending")  # pending, accepted, rejected, countered
    parent_offer_id = Column(String, ForeignKey("offers.id"), nullable=True)
    message = Column(Text, nullable=True)
    correlation_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Negotiation(Base):
    __tablename__ = "negotiations"

    id = Column(String, primary_key=True, default=gen_uuid)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    buyer_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    seller_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    status = Column(Enum(NegotiationStatus), default=NegotiationStatus.IDLE)
    round_count = Column(Integer, default=0)
    final_price = Column(Float, nullable=True)
    correlation_id = Column(String, nullable=True, index=True)
    deadline_at = Column(DateTime, nullable=True)
    state_entered_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id = Column(String, primary_key=True, default=gen_uuid)
    agent_type = Column(String, nullable=False)  # buyer, seller, broker
    negotiation_id = Column(String, ForeignKey("negotiations.id"), nullable=True)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=True)
    action = Column(String, nullable=False)
    reasoning = Column(Text)
    tool_used = Column(String)
    tool_input = Column(JSONB)
    tool_output = Column(JSONB)
    correlation_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentMemory(Base):
    __tablename__ = "agent_memory"

    id = Column(String, primary_key=True, default=gen_uuid)
    agent_type = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    key = Column(String, nullable=False)
    value = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MiroFishReport(Base):
    __tablename__ = "mirofish_reports"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    seed_hash = Column(String)
    simulation_config = Column(JSONB, default=dict)
    report_json = Column(JSONB, default=dict)
    status = Column(String, default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)


class MiroFishSeed(Base):
    __tablename__ = "mirofish_seeds"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    seed_text = Column(Text)
    market_data_snapshot = Column(JSONB, default=dict)
    listings_snapshot = Column(JSONB, default=list)
    assembled_at = Column(DateTime, default=datetime.utcnow)


class SimulationResult(Base):
    """Persisted negotiation simulation results, linked to user who ran them."""
    __tablename__ = "simulation_results"
    __table_args__ = (
        Index("ix_simulation_results_user_created", "user_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    property_id = Column(String, nullable=False)  # not FK — sim may use placeholder IDs
    batch_id = Column(String, nullable=True, index=True)
    scenario_name = Column(String, nullable=True)
    outcome = Column(String, nullable=False)  # accepted, rejected, max_rounds, broker_stopped
    final_price = Column(Float, nullable=True)
    asking_price = Column(Float, nullable=False)
    initial_offer = Column(Float, nullable=False)
    rounds_completed = Column(Integer, default=0)
    max_rounds = Column(Integer, default=10)
    strategy = Column(String, default="balanced")
    summary = Column(JSONB, default=dict)
    price_path = Column(JSONB, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Social Simulation Models ──


class CommunicationStyle(str, enum.Enum):
    VOCAL = "vocal"
    PASSIVE = "passive"
    ANALYTICAL = "analytical"
    EMOTIONAL = "emotional"


class HouseholdProfile(Base):
    """Synthetic household for social behavior simulation."""
    __tablename__ = "household_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
    # Demographics
    name = Column(String, nullable=False)
    zip_code = Column(String, nullable=False)
    income_band = Column(String, nullable=False)  # "low", "moderate", "middle", "upper"
    household_size = Column(Integer, default=2)
    num_children = Column(Integer, default=0)
    primary_language = Column(String, default="english")
    age_bracket = Column(String, default="30-45")  # "18-29", "30-45", "46-64", "65+"
    housing_type = Column(String, default="renter")  # "renter", "owner", "voucher"
    has_housing_voucher = Column(Integer, default=0)  # 0 or 1
    monthly_housing_cost = Column(Float, default=0)
    monthly_income = Column(Float, default=0)
    eviction_risk = Column(Float, default=0.0)  # 0.0 to 1.0

    # Opinion & Social fields
    housing_market_sentiment = Column(Float, default=0.0)   # -1.0 (bearish) to +1.0 (bullish)
    policy_support_score = Column(Float, default=0.0)       # -1.0 (opposed) to +1.0 (supportive)
    neighborhood_satisfaction = Column(Float, default=0.5)   # 0.0 to 1.0
    influence_weight = Column(Float, default=0.5)            # 0.1 to 1.0
    communication_style = Column(Enum(CommunicationStyle), default=CommunicationStyle.PASSIVE)
    social_connections = Column(Integer, default=0)
    opinion_stability = Column(Float, default=0.5)           # 0=volatile, 1=rigid

    # Metadata
    persona_data = Column(JSONB, default=dict)  # additional personality traits
    created_at = Column(DateTime, default=datetime.utcnow)


class HouseholdSocialEdge(Base):
    """Edge in the social graph between two households."""
    __tablename__ = "household_social_edges"
    __table_args__ = (
        Index("ix_social_edges_source", "source_id"),
        Index("ix_social_edges_target", "target_id"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    source_id = Column(String, ForeignKey("household_profiles.id"), nullable=False)
    target_id = Column(String, ForeignKey("household_profiles.id"), nullable=False)
    edge_weight = Column(Float, default=0.5)       # 0.0 to 1.0 (strength of influence)
    edge_type = Column(String, nullable=False)      # "neighbor", "income_peer", "language_peer", "demographic"
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("HouseholdProfile", foreign_keys=[source_id])
    target = relationship("HouseholdProfile", foreign_keys=[target_id])


class SocialSimulationRun(Base):
    """Tracks a social behavior simulation execution."""
    __tablename__ = "social_simulation_runs"

    id = Column(String, primary_key=True, default=gen_uuid)
    trigger_user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    household_filter = Column(JSONB, default=dict)   # which households were included
    household_ids = Column(JSONB, default=list)
    household_count = Column(Integer, default=0)
    total_rounds = Column(Integer, default=10)
    current_round = Column(Integer, default=0)
    status = Column(String, default="preparing")     # preparing, running, completed, failed
    topics = Column(JSONB, default=list)             # ["market_prices", "eviction_policy", ...]
    narrative_output = Column(JSONB, default=dict)    # final evolved narratives per topic
    sentiment_delta = Column(JSONB, default=dict)     # how opinions shifted across rounds
    report_id = Column(String, ForeignKey("mirofish_reports.id"), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class SocialSimulationAction(Base):
    """Individual household action within a social simulation round."""
    __tablename__ = "social_simulation_actions"
    __table_args__ = (
        Index("ix_social_actions_run_round", "run_id", "round_num"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    run_id = Column(String, ForeignKey("social_simulation_runs.id"), nullable=False)
    round_num = Column(Integer, nullable=False)
    household_id = Column(String, ForeignKey("household_profiles.id"), nullable=False)
    action_type = Column(String, nullable=False)     # "post_opinion", "share_narrative", "update_stance", "go_silent"
    topic = Column(String, nullable=False)           # "market_prices", "eviction_policy", "voucher_program", "neighborhood_safety"
    content = Column(Text)                           # LLM-generated opinion text
    sentiment_value = Column(Float)                  # resulting sentiment after this action
    influenced_by = Column(JSONB, default=list)      # list of household_ids that swayed this action
    created_at = Column(DateTime, default=datetime.utcnow)


class DomainEvent(Base):
    """Append-only event sourcing table."""
    __tablename__ = "domain_events"
    __table_args__ = (
        Index("ix_domain_events_aggregate", "aggregate_type", "aggregate_id"),
        Index("ix_domain_events_correlation", "correlation_id"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    correlation_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)
    aggregate_type = Column(String, nullable=False)
    aggregate_id = Column(String, nullable=False)
    payload = Column(JSONB, default=dict)
    actor_type = Column(String, nullable=True)  # user, agent, system
    actor_id = Column(String, nullable=True)
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketSignal(Base):
    """Spatial-market signal store (Phase B).

    Single table for transit/school/hazard/comp/zoning/rent/sentiment signals
    keyed by ``(signal_type, subject_type, subject_id)``. Numeric scalars go in
    ``value``; structured detail (per-hazard flags, comp metadata) lives in
    ``payload``. The market-state snapshot builder reads the latest row per
    ``signal_type`` for a given subject.
    """

    __tablename__ = "market_signals"
    __table_args__ = (
        Index("ix_market_signals_subject", "subject_type", "subject_id"),
        Index("ix_market_signals_type_observed", "signal_type", "observed_at"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    signal_type = Column(String, nullable=False)
    subject_type = Column(String, nullable=False)
    subject_id = Column(String, nullable=False)
    value = Column(Float, nullable=True)
    payload = Column(JSONB, default=dict)
    source = Column(String, nullable=True)
    observed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketSimulationRun(Base):
    """Persistent market-wide investor simulation run."""

    __tablename__ = "market_simulation_runs"
    __table_args__ = (
        Index("ix_market_sim_runs_status_created", "status", "created_at"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    run_label = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, running, completed, failed
    property_scope = Column(JSONB, default=dict)
    cohort_preset = Column(String, default="balanced")
    investor_count = Column(Integer, default=0)
    property_count = Column(Integer, default=0)
    total_ticks = Column(Integer, default=10)
    current_tick = Column(Integer, default=0)
    summary = Column(JSONB, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class MarketSimulationInvestor(Base):
    """Synthetic investor snapshot persisted per market simulation run."""

    __tablename__ = "market_simulation_investors"
    __table_args__ = (
        Index("ix_market_sim_investors_run", "run_id"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    run_id = Column(String, ForeignKey("market_simulation_runs.id"), nullable=False)
    investor_name = Column(String, nullable=False)
    archetype = Column(String, nullable=False)
    budget = Column(Float, nullable=False)
    cash_remaining = Column(Float, nullable=False)
    hold_horizon_ticks = Column(Integer, default=6)
    risk_appetite = Column(Float, default=0.5)
    diversification_cap = Column(Integer, default=2)
    preferred_property_types = Column(JSONB, default=list)
    signal_weights = Column(JSONB, default=dict)
    persona_profile = Column(JSONB, default=dict)
    holdings = Column(JSONB, default=list)
    metadata_json = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketSimulationPropertyState(Base):
    """Aggregated per-property state for each simulation tick."""

    __tablename__ = "market_simulation_property_states"
    __table_args__ = (
        Index("ix_market_sim_property_state_run_tick", "run_id", "tick_num"),
        Index("ix_market_sim_property_state_property", "property_id", "tick_num"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    run_id = Column(String, ForeignKey("market_simulation_runs.id"), nullable=False)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    tick_num = Column(Integer, nullable=False)
    status = Column(String, default="active")
    attention_count = Column(Integer, default=0)
    bid_count = Column(Integer, default=0)
    top_bid = Column(Float, nullable=True)
    bid_velocity = Column(Float, default=0.0)
    local_competition = Column(Float, default=0.0)
    recent_attention = Column(Float, default=0.0)
    reservation_threshold = Column(Float, nullable=False)
    winning_investor_id = Column(
        String,
        ForeignKey("market_simulation_investors.id"),
        nullable=True,
    )
    signal_snapshot = Column(JSONB, default=dict)
    targeted_investor_ids = Column(JSONB, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketSimulationDecision(Base):
    """One investor decision per tick, with explanation payload."""

    __tablename__ = "market_simulation_decisions"
    __table_args__ = (
        Index("ix_market_sim_decision_run_tick", "run_id", "tick_num"),
        Index("ix_market_sim_decision_investor_tick", "investor_id", "tick_num"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    run_id = Column(String, ForeignKey("market_simulation_runs.id"), nullable=False)
    tick_num = Column(Integer, nullable=False)
    investor_id = Column(String, ForeignKey("market_simulation_investors.id"), nullable=False)
    property_id = Column(String, ForeignKey("properties.id"), nullable=True)
    chosen_action = Column(String, nullable=False)
    bid_amount = Column(Float, nullable=True)
    total_score = Column(Float, nullable=True)
    score_breakdown = Column(JSONB, default=dict)
    explanation_payload = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Investor Portfolio Models (Phase P1) ──────────────────────────────────


class InvestorPortfolio(Base):
    """Individual-investor portfolio aggregate."""

    __tablename__ = "investor_portfolios"
    __table_args__ = (Index("ix_investor_portfolios_user", "user_id"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    name = Column(String, nullable=False)
    investment_strategy = Column(
        Enum(InvestmentStrategy), default=InvestmentStrategy.BUY_HOLD, nullable=False
    )
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PortfolioHolding(Base):
    """A single property within an investor's portfolio.

    ``property_id`` is nullable so off-platform holdings (not in the listings
    catalog) can still be tracked by free-text address.
    """

    __tablename__ = "portfolio_holdings"
    __table_args__ = (
        Index("ix_portfolio_holdings_portfolio", "portfolio_id"),
        Index("ix_portfolio_holdings_property", "property_id"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    portfolio_id = Column(
        String, ForeignKey("investor_portfolios.id"), nullable=False
    )
    property_id = Column(String, ForeignKey("properties.id"), nullable=True)
    address = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    zip_code = Column(String, nullable=True)
    asset_class = Column(Enum(AssetClass), default=AssetClass.SFR, nullable=False)
    status = Column(Enum(HoldingStatus), default=HoldingStatus.HELD, nullable=False)
    acquisition_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HoldingFinancials(Base):
    """Mutable financial snapshot for a holding (current rent, debt, opex).

    1:1 with PortfolioHolding (in practice). All money fields in USD; rates as
    decimal fractions (0.065 == 6.5%).
    """

    __tablename__ = "holding_financials"
    __table_args__ = (Index("ix_holding_financials_holding", "holding_id"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    holding_id = Column(
        String, ForeignKey("portfolio_holdings.id"), nullable=False
    )
    cost_basis = Column(Float, nullable=True)
    current_value_estimate = Column(Float, nullable=True)
    value_estimate_source = Column(String, nullable=True)  # acs, zillow, user, ...
    loan_balance = Column(Float, nullable=True)
    interest_rate = Column(Float, nullable=True)
    loan_maturity = Column(DateTime, nullable=True)
    monthly_piti = Column(Float, nullable=True)
    monthly_rent = Column(Float, nullable=True)
    vacancy_rate = Column(Float, nullable=True, default=0.05)
    monthly_opex_estimate = Column(Float, nullable=True)
    property_tax_annual = Column(Float, nullable=True)
    insurance_annual = Column(Float, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class InvestorProfile(Base):
    """Investor goals + constraints captured by the onboarding wizard.

    One row per user. Drives the property recommendation ranker. Mutable —
    later edits upsert in place by ``user_id``.
    """

    __tablename__ = "investor_profiles"
    __table_args__ = (Index("ix_investor_profiles_user", "user_id", unique=True),)

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    budget = Column(Float, nullable=True)
    strategy = Column(String, nullable=True)  # buy_and_hold | flip | lease
    target_cap_rate = Column(Float, nullable=True)  # %, e.g. 7.5
    target_coc = Column(Float, nullable=True)  # %, e.g. 8.0
    geography = Column(JSONB, nullable=False, default=dict)  # {zip,city,state}
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UnderwritingScenario(Base):
    """Persisted underwriting + stress-test scenario.

    ``holding_id`` is nullable so a pre-purchase analysis (no holding yet) can
    still be saved. Inputs/outputs/hazard signals are JSONB blobs so the
    schema doesn't need to migrate every time we add a new slider.
    """

    __tablename__ = "underwriting_scenarios"
    __table_args__ = (
        Index("ix_underwriting_scenarios_holding", "holding_id"),
        Index("ix_underwriting_scenarios_created", "created_at"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    holding_id = Column(
        String, ForeignKey("portfolio_holdings.id"), nullable=True
    )
    correlation_id = Column(String, nullable=True)
    label = Column(String, nullable=True)
    inputs = Column(JSONB, default=dict)
    outputs = Column(JSONB, default=dict)
    hazard_signals = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
