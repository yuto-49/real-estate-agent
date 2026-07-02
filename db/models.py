"""SQLAlchemy models — JP investor portfolio analytics scope.

Removed in pivot (see migration f9a1b2c3d4e5): negotiation/offer chat product,
household social-sim, MiroFish stubs, synthetic market-tick simulation.
"""

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column, String, Float, Integer, Numeric, Text, DateTime, ForeignKey, Enum, Index
)
from sqlalchemy.dialects.postgresql import JSONB

from db.database import Base


def gen_uuid():
    return str(uuid4())


# ── Enums ───────────────────────────────────────────────────────────────


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


class PropertyStatus(str, enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"


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


# ── JP listing-tier enums (Phase 2A) ───────────────────────────────────


class AssetTier(str, enum.Enum):
    """Tokyo workforce-housing asset tier — drives recommender + analyst council."""

    ONE_ROOM = "one_room"          # ワンルーム 20-30 m² studio, station-proximity yield play
    APARUTO = "aparuto"            # 4-12 unit wood/light-steel, depreciation tax shield
    FAMILY_MANSION = "family_mansion"  # 55-80 m² 2LDK/3LDK East-Tokyo migration


class ConstructionType(str, enum.Enum):
    """Drives statutory depreciation useful-life table (法定耐用年数)."""

    WOOD = "wood"                   # 木造 — 22年
    LIGHT_STEEL = "light_steel"     # 軽量鉄骨 — 27年
    STEEL = "steel"                 # 鉄骨 — 34年
    RC = "rc"                       # 鉄筋コンクリート — 47年
    SRC = "src"                     # 鉄骨鉄筋コンクリート — 47年


class SeismicCode(str, enum.Enum):
    """Pre/post 1981-06-01 building standard — financeability + insurance signal."""

    KYU_TAISHIN = "kyu_taishin"     # 旧耐震 (before 1981-06)
    SHIN_TAISHIN = "shin_taishin"   # 新耐震 (1981-06 onward)


# ── Core tables ─────────────────────────────────────────────────────────


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
    supabase_user_id = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    role = Column(String, default="buyer")
    budget_min = Column(Float)
    budget_max = Column(Float)
    life_stage = Column(Enum(LifeStage))
    investment_goals = Column(JSONB, default=dict)
    risk_tolerance = Column(Enum(RiskTolerance), default=RiskTolerance.MODERATE)
    timeline_days = Column(Integer, default=90)
    latitude = Column(Float)
    longitude = Column(Float)
    zip_code = Column(String)
    search_radius = Column(Integer, default=10)
    preferred_types = Column(JSONB, default=list)
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
    property_type = Column(String)
    hoa_fees = Column(Float, default=0)
    disclosures = Column(JSONB, default=dict)
    neighborhood_data = Column(JSONB, default=dict)
    status = Column(Enum(PropertyStatus), default=PropertyStatus.ACTIVE)
    listed_at = Column(DateTime, default=datetime.utcnow)

    # ── JP-native columns ──
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

    # ── JP tier discriminators (Phase 2A) ──
    asset_tier = Column(
        Enum(AssetTier, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
        index=True,
    )
    construction_type = Column(
        Enum(ConstructionType, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    seismic_code = Column(
        Enum(SeismicCode, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    re_buildable = Column(Integer, nullable=True)  # 1/0/null — 再建築可否
    road_frontage_m = Column(Float, nullable=True)
    ward_code = Column(String(8), nullable=True, index=True)
    walk_minutes_to_station = Column(Integer, nullable=True)
    assumed_monthly_rent_yen = Column(Integer, nullable=True)
    occupancy_rate = Column(Float, nullable=True)


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
    actor_type = Column(String, nullable=True)
    actor_id = Column(String, nullable=True)
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketSignal(Base):
    """Spatial-market signal store keyed by (signal_type, subject_type, subject_id)."""

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


# ── Investor portfolio (Phase P1) ──────────────────────────────────────


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

    ``property_id`` is nullable so off-platform holdings can still be tracked.
    """

    __tablename__ = "portfolio_holdings"
    __table_args__ = (
        Index("ix_portfolio_holdings_portfolio", "portfolio_id"),
        Index("ix_portfolio_holdings_property", "property_id"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    portfolio_id = Column(String, ForeignKey("investor_portfolios.id"), nullable=False)
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
    """Mutable financial snapshot for a holding."""

    __tablename__ = "holding_financials"
    __table_args__ = (Index("ix_holding_financials_holding", "holding_id"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    holding_id = Column(String, ForeignKey("portfolio_holdings.id"), nullable=False)
    cost_basis = Column(Float, nullable=True)
    current_value_estimate = Column(Float, nullable=True)
    value_estimate_source = Column(String, nullable=True)
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
    """Investor goals + constraints captured by the onboarding wizard."""

    __tablename__ = "investor_profiles"
    __table_args__ = (Index("ix_investor_profiles_user", "user_id", unique=True),)

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    budget = Column(Float, nullable=True)
    strategy = Column(String, nullable=True)
    target_cap_rate = Column(Float, nullable=True)
    target_coc = Column(Float, nullable=True)
    geography = Column(JSONB, nullable=False, default=dict)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UnderwritingScenario(Base):
    """Persisted underwriting + stress-test scenario."""

    __tablename__ = "underwriting_scenarios"
    __table_args__ = (
        Index("ix_underwriting_scenarios_holding", "holding_id"),
        Index("ix_underwriting_scenarios_created", "created_at"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    holding_id = Column(String, ForeignKey("portfolio_holdings.id"), nullable=True)
    correlation_id = Column(String, nullable=True)
    label = Column(String, nullable=True)
    inputs = Column(JSONB, default=dict)
    outputs = Column(JSONB, default=dict)
    hazard_signals = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class RentComp(Base):
    """Comparable rental listing used for rent validation."""

    __tablename__ = "rent_comps"
    __table_args__ = (
        Index("ix_rent_comps_zip", "zip_code"),
        Index("ix_rent_comps_ward", "ward_code"),
        Index("ix_rent_comps_property", "property_id"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    property_id = Column(String, ForeignKey("properties.id"), nullable=True)
    zip_code = Column(String, nullable=False)
    ward_code = Column(String, nullable=True)

    # Comp data
    source = Column(String, nullable=False)                # "suumo", "homes", "lifull", "manual"
    source_listing_id = Column(String, nullable=True)
    address_hint = Column(String, nullable=True)
    menseki_m2 = Column(Float, nullable=True)
    madori = Column(String, nullable=True)                 # "1K", "1LDK", "2LDK"
    walk_minutes = Column(Integer, nullable=True)
    monthly_rent_yen = Column(Integer, nullable=False)
    management_fee_yen = Column(Integer, nullable=True)
    built_year = Column(Integer, nullable=True)
    construction_type = Column(String, nullable=True)

    fetched_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)           # stale after 30 days


class SaleComp(Base):
    """Comparable sale transaction from REINFOLIB for satei valuation."""

    __tablename__ = "sale_comps"
    __table_args__ = (
        Index("ix_sale_comps_zip", "zip_code"),
        Index("ix_sale_comps_ward", "ward_code"),
        Index("ix_sale_comps_city", "city_code"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    city_code = Column(String, nullable=False)
    zip_code = Column(String, nullable=True)
    ward_code = Column(String, nullable=True)

    source = Column(String, nullable=False, default="reinfolib")
    source_record_id = Column(String, nullable=True)
    address_hint = Column(String, nullable=True)
    trade_price_yen = Column(Integer, nullable=False)
    unit_price_yen = Column(Integer, nullable=True)
    menseki_m2 = Column(Float, nullable=True)
    built_year = Column(Integer, nullable=True)
    construction_type = Column(String, nullable=True)
    walk_minutes = Column(Integer, nullable=True)
    floor_level = Column(Integer, nullable=True)
    transaction_year = Column(Integer, nullable=True)
    transaction_quarter = Column(Integer, nullable=True)

    fetched_at = Column(DateTime, default=datetime.utcnow)


class SateiSession(Base):
    """Persisted satei (valuation) session with comp grid and result."""

    __tablename__ = "satei_sessions"
    __table_args__ = (
        Index("ix_satei_sessions_user", "user_id"),
        Index("ix_satei_sessions_created", "created_at"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=True)
    property_id = Column(String, ForeignKey("properties.id"), nullable=True)

    address = Column(String, nullable=True)
    menseki_m2 = Column(Float, nullable=True)
    built_year = Column(Integer, nullable=True)
    construction_type = Column(String, nullable=True)
    walk_minutes = Column(Integer, nullable=True)

    satei_price_yen = Column(Integer, nullable=True)
    confidence_low_yen = Column(Integer, nullable=True)
    confidence_high_yen = Column(Integer, nullable=True)
    comp_count = Column(Integer, nullable=True)
    adjustment_grid = Column(JSONB, default=list)
    result_payload = Column(JSONB, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
