"""Buyer simulation orchestration service.

Loads property and market signal data from the database, runs the
GNN-powered buyer simulation, and generates a report comparing results
with the existing satei and price-probability engines.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketSignal, Property, SaleComp
from domain.buyer_sim.buyer_generator import generate_buyers
from domain.buyer_sim.environment import BuyerSimEnvironment
from domain.buyer_sim.feature_extractor import DEFAULT_NORMALIZATION, extract_features
from domain.buyer_sim.models import BuyerSimConfig, BuyerSimReport, PropertyFeatures
from domain.buyer_sim.report import generate_report
from services.price_probability import compute_price_probability_curve
from services.satei_engine import compute_satei

logger = structlog.get_logger(__name__)


async def _load_property(db: AsyncSession, property_id: str) -> Property | None:
    """Load a single property by ID."""
    stmt = select(Property).where(Property.id == property_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _load_nearby_properties(
    db: AsyncSession,
    target: Property,
    limit: int = 20,
) -> list[Property]:
    """Load nearby active properties, preferring same ward.

    Falls back to all active properties when ward_code is unavailable.
    """
    stmt = select(Property).where(
        Property.status == "active",
        Property.id != target.id,
    )
    if target.ward_code:
        stmt = stmt.where(Property.ward_code == target.ward_code)

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    props = list(result.scalars().all())

    # If ward filter yielded too few, broaden to all active properties.
    if len(props) < 5 and target.ward_code:
        stmt_broad = (
            select(Property)
            .where(Property.status == "active", Property.id != target.id)
            .limit(limit)
        )
        result_broad = await db.execute(stmt_broad)
        props = list(result_broad.scalars().all())

    return props


async def _load_hazard_signals(
    db: AsyncSession,
    property_id: str,
) -> dict[str, float]:
    """Load hazard-related market signals for a property.

    Returns a dict with keys: hazard_flood, hazard_liquefaction,
    hazard_landslide, median_sale_price, land_price.
    Defaults to 0.0 for any missing signal.
    """
    stmt = (
        select(MarketSignal)
        .where(
            MarketSignal.subject_type == "property",
            MarketSignal.subject_id == property_id,
        )
        .order_by(MarketSignal.observed_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    signals: dict[str, float] = {
        "hazard_flood": 0.0,
        "hazard_liquefaction": 0.0,
        "hazard_landslide": 0.0,
        "median_sale_price": 0.0,
        "land_price": 0.0,
    }

    for row in rows:
        sig_type = row.signal_type or ""
        if sig_type in signals and row.value is not None:
            # Keep only the first (most recent) value per signal type.
            if signals[sig_type] == 0.0:
                signals[sig_type] = float(row.value)

    return signals


def _property_to_dict(prop: Property) -> dict:
    """Convert a Property ORM row to the dict expected by extract_features."""
    asking_price = int(prop.baibai_kakaku_yen or prop.asking_price or 0)
    return {
        "property_id": prop.id,
        "latitude": float(prop.latitude or 0.0),
        "longitude": float(prop.longitude or 0.0),
        "menseki_m2": float(prop.menseki_m2 or 0.0),
        "built_year": int(prop.built_year or 1990),
        "walk_minutes": int(prop.walk_minutes_to_station or 10),
        "construction_type": str(prop.construction_type.value if prop.construction_type else ""),
        "seismic_code": str(prop.seismic_code.value if prop.seismic_code else ""),
        "asset_tier": str(prop.asset_tier.value if prop.asset_tier else ""),
        "asking_price_yen": asking_price,
        "kanrihi": int(prop.kanrihi_yen or 0),
        "occupancy_rate": float(prop.occupancy_rate or 1.0),
        "re_buildable": int(prop.re_buildable) if prop.re_buildable is not None else 1,
        "cap_rate": 0.0,
    }


async def run_buyer_simulation(
    db: AsyncSession,
    property_id: str,
    n_buyers: int = 50,
    max_rounds: int = 15,
    seed: int | None = None,
) -> BuyerSimReport:
    """Run a full buyer simulation for a property and return a report.

    Steps
    -----
    1. Load the target property from the database.
    2. Load nearby properties (same ward or up to 20 active).
    3. Load hazard / market signals for each property.
    4. Convert to PropertyFeatures via extract_features.
    5. Generate buyer profiles.
    6. Run the GNN simulation.
    7. Compute satei and price-probability for comparison (best-effort).
    8. Generate and return the BuyerSimReport.
    """
    # 1. Load target property
    target = await _load_property(db, property_id)
    if target is None:
        raise ValueError(f"Property not found: {property_id}")

    logger.info(
        "buyer_simulation.start",
        property_id=property_id,
        n_buyers=n_buyers,
        max_rounds=max_rounds,
    )

    # 2. Load nearby properties
    nearby = await _load_nearby_properties(db, target, limit=20)
    all_properties = [target, *nearby]

    # 3 & 4. Convert each property to PropertyFeatures
    property_features: list[PropertyFeatures] = []
    for prop in all_properties:
        signals = await _load_hazard_signals(db, prop.id)
        prop_dict = _property_to_dict(prop)
        # Merge hazard signals into property_data for extract_features
        prop_dict["hazard_flood"] = signals["hazard_flood"]
        prop_dict["hazard_liquefaction"] = signals["hazard_liquefaction"]
        prop_dict["hazard_landslide"] = signals["hazard_landslide"]

        market_signals = {
            "median_sale_price": signals["median_sale_price"],
            "land_price": signals["land_price"],
        }

        features = extract_features(prop_dict, market_signals, DEFAULT_NORMALIZATION)
        property_features.append(features)

    # 5. Generate buyer profiles
    buyers = list(generate_buyers(n_buyers, seed=seed))

    # 6. Run simulation
    config = BuyerSimConfig(
        max_rounds=max_rounds,
        n_buyers=n_buyers,
        seed=seed,
    )
    env = BuyerSimEnvironment(config)
    env.reset(property_features, buyers)
    sim_result = env.run()

    logger.info(
        "buyer_simulation.complete",
        property_id=property_id,
        converged=sim_result.converged,
        rounds=len(sim_result.rounds),
    )

    # 7. Compute satei and price-probability for comparison (best-effort)
    satei_price_yen: int | None = None
    sweet_spot_yen: int | None = None

    try:
        satei_result = await compute_satei(
            db,
            city_code=target.ward_code,
            menseki_m2=target.menseki_m2,
            built_year=target.built_year,
            construction_type=(
                target.construction_type.value if target.construction_type else None
            ),
            walk_minutes=(
                target.walk_minutes_to_station
                if target.walk_minutes_to_station is not None
                else None
            ),
        )
        if satei_result.comp_count > 0:
            satei_price_yen = satei_result.satei_price_yen
    except Exception:
        logger.warning("buyer_simulation.satei_fallback", property_id=property_id)

    if satei_price_yen and satei_price_yen > 0:
        try:
            curve = compute_price_probability_curve(satei_price_yen=satei_price_yen)
            sweet_spot_yen = _find_sweet_spot(curve)
        except Exception:
            logger.warning(
                "buyer_simulation.price_prob_fallback",
                property_id=property_id,
            )

    # 8. Generate report
    report = generate_report(
        property_id=property_id,
        sim_result=sim_result,
        satei_price_yen=satei_price_yen,
        price_prob_sweet_spot_yen=sweet_spot_yen,
    )

    return report


def _find_sweet_spot(curve) -> int | None:  # noqa: ANN001
    """Extract sweet-spot yen from a PriceProbabilityCurve if present.

    Looks for the point with highest p90 * expected_settlement_yen product.
    """
    if not curve or not curve.points:
        return None
    best = max(curve.points, key=lambda p: p.p90 * p.expected_settlement_yen)
    return best.expected_settlement_yen
