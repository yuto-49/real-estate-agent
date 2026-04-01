"""SQLAlchemy models — maps directly to Section 8 of the spec."""

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column, String, Float, Integer, Text, DateTime, ForeignKey, Enum, Index
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


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
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


class Offer(Base):
    __tablename__ = "offers"

    id = Column(String, primary_key=True, default=gen_uuid)
    property_id = Column(String, ForeignKey("properties.id"), nullable=False)
    buyer_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    offer_price = Column(Float, nullable=False)
    contingencies = Column(JSONB, default=list)
    status = Column(String, default="pending")  # pending, accepted, rejected, countered
    parent_offer_id = Column(String, ForeignKey("offers.id"), nullable=True)
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
