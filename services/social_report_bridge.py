"""Social Simulation -> MiroFish Report Bridge.

Translates SocialSimulationRun output into MiroFishReport.report_json format
so the existing negotiation simulator can consume it unchanged via
_build_intelligence_briefings().
"""

from typing import Any, cast

from sqlalchemy import select, update

from db.database import async_session
from db.models import (
    HouseholdProfile,
    MiroFishReport,
    Property,
    SocialSimulationRun,
)


def _derive_trend(sentiment_delta: dict[str, Any]) -> str:
    """Map market_prices sentiment shift to a market trend label."""
    market = sentiment_delta.get("market_prices", {})
    final_avg = market.get("final_avg", 0)
    if final_avg > 0.3:
        return "bullish"
    elif final_avg > 0.1:
        return "cautiously_optimistic"
    elif final_avg > -0.1:
        return "neutral"
    elif final_avg > -0.3:
        return "cautiously_bearish"
    return "bearish"


def _map_sentiment_to_health_score(
    narrative_output: dict[str, Any],
) -> int:
    """Map overall community sentiment to a 0-100 health score."""
    scores: list[float] = []
    for _topic, data in narrative_output.items():
        avg = data.get("avg_opinion", 0)
        consensus = data.get("consensus_strength", 0.5)
        # Positive sentiment + high consensus = healthy
        scores.append((avg + 1) / 2 * 50 + consensus * 50)
    return int(sum(scores) / len(scores)) if scores else 50


def _derive_risk(
    run: SocialSimulationRun,
    household: HouseholdProfile,
) -> float:
    """Estimate probability of loss from sentiment and household risk."""
    sentiment = cast(dict[str, Any], run.sentiment_delta or {})
    market_shift = sentiment.get(
        "market_prices", {},
    ).get("shift", 0)
    safety_avg = sentiment.get(
        "neighborhood_safety", {},
    ).get("final_avg", 0)

    # Base risk from household eviction risk
    base = float(cast(float, household.eviction_risk))

    # Market bearishness increases risk
    if market_shift < -0.1:
        base += abs(market_shift) * 0.3

    # Poor neighborhood sentiment increases risk
    if safety_avg < -0.2:
        base += abs(safety_avg) * 0.2

    return round(min(1.0, max(0.0, base)), 3)


def _extract_risk_narratives(
    run: SocialSimulationRun,
    household: HouseholdProfile,
) -> list[dict[str, Any]]:
    """Extract risk factors from simulation narratives."""
    risks: list[dict[str, Any]] = []
    narratives = cast(dict[str, Any], run.narrative_output or {})

    # Eviction policy risk
    eviction = narratives.get("eviction_policy", {})
    if eviction.get("dominant_stance") == "opposed":
        consensus = eviction.get("consensus_strength", 0)
        opposed_count = eviction.get("opposed_count", 0)
        risks.append({
            "factor": "weak_tenant_protections",
            "severity": "high" if consensus > 0.6 else "medium",
            "probability": round(0.3 + consensus * 0.3, 2),
            "description": (
                "Community sentiment opposes current eviction "
                f"policies ({opposed_count} households opposed)"
            ),
        })

    # Neighborhood safety risk
    safety = narratives.get("neighborhood_safety", {})
    avg_opinion = safety.get("avg_opinion", 0)
    if avg_opinion < -0.1:
        risks.append({
            "factor": "neighborhood_safety_concern",
            "severity": "high" if avg_opinion < -0.3 else "medium",
            "probability": round(0.4 + abs(avg_opinion) * 0.3, 2),
            "description": (
                "Community perceives safety negatively "
                f"(avg: {avg_opinion:.2f})"
            ),
        })

    # Market volatility risk
    delta = cast(dict[str, Any], run.sentiment_delta or {})
    market_vol = delta.get("market_prices", {}).get("volatility", 0)
    if market_vol > 0.15:
        risks.append({
            "factor": "market_sentiment_volatility",
            "severity": "medium",
            "probability": round(min(0.8, market_vol), 2),
            "description": (
                "High opinion volatility around market prices "
                f"(volatility: {market_vol:.3f})"
            ),
        })

    # Voucher program risk (for voucher holders)
    if household.has_housing_voucher:
        voucher = narratives.get("voucher_program", {})
        if voucher.get("dominant_stance") == "opposed":
            v_consensus = voucher.get("consensus_strength", 0)
            risks.append({
                "factor": "voucher_acceptance_risk",
                "severity": "high",
                "probability": round(0.4 + v_consensus * 0.3, 2),
                "description": (
                    "Community opposition to voucher programs "
                    "may limit housing options"
                ),
            })

    return risks


def _derive_strategies(
    run: SocialSimulationRun,
    household: HouseholdProfile,
) -> list[dict[str, Any]]:
    """Generate strategy recommendations from social simulation output."""
    narratives = cast(dict[str, Any], run.narrative_output or {})
    delta = cast(dict[str, Any], run.sentiment_delta or {})

    market_trend = _derive_trend(delta)
    market_consensus = narratives.get(
        "market_prices", {},
    ).get("consensus_strength", 0.5)

    strategies: list[dict[str, Any]] = []

    # Conservative strategy
    bearish_trends = ("bearish", "cautiously_bearish")
    conservative_pct = 92 if market_trend in bearish_trends else 95
    strategies.append({
        "name": "Conservative",
        "recommended_offer_pct": conservative_pct,
        "success_probability": (
            0.75 if market_consensus > 0.5 else 0.60
        ),
        "description": (
            "Lower offer leveraging community concern "
            "about market conditions"
        ),
    })

    # Balanced strategy
    strategies.append({
        "name": "Balanced",
        "recommended_offer_pct": 95,
        "success_probability": 0.65,
        "description": (
            "Market-aligned offer informed by community sentiment"
        ),
    })

    # Aggressive strategy
    bullish_trends = ("bullish", "cautiously_optimistic")
    aggressive_pct = 98 if market_trend in bullish_trends else 96
    strategies.append({
        "name": "Aggressive",
        "recommended_offer_pct": aggressive_pct,
        "success_probability": (
            0.50 if market_trend == "bullish" else 0.40
        ),
        "description": (
            "Higher offer to compete in a community "
            "with positive market sentiment"
        ),
    })

    return strategies


def _get_peer_group_opinion(
    run: SocialSimulationRun,
    household: HouseholdProfile,
) -> dict[str, Any]:
    """Extract opinions from households in the same income band."""
    narratives = cast(dict[str, Any], run.narrative_output or {})
    income = cast(str, household.income_band)

    peer_data: dict[str, Any] = {}
    for topic, data in narratives.items():
        income_breakdown = data.get("income_breakdown", {})
        band_data = income_breakdown.get(income, {})
        total = sum(band_data.values()) if band_data else 0
        if total > 0:
            peer_data[topic] = {
                "supportive_pct": round(
                    band_data.get("supportive", 0) / total * 100, 1,
                ),
                "opposed_pct": round(
                    band_data.get("opposed", 0) / total * 100, 1,
                ),
                "neutral_pct": round(
                    band_data.get("neutral", 0) / total * 100, 1,
                ),
            }
    return peer_data


def build_report_from_social_sim(
    run: SocialSimulationRun,
    target_household: HouseholdProfile,
    property_data: dict[str, Any],
) -> dict[str, Any]:
    """Build a MiroFishReport-compatible report_json.

    This is the bridge that allows the existing negotiation simulator
    to consume social simulation intelligence without code changes.
    """
    narratives = cast(dict[str, Any], run.narrative_output or {})
    delta = cast(dict[str, Any], run.sentiment_delta or {})

    market_trend = _derive_trend(delta)
    health_score = _map_sentiment_to_health_score(narratives)

    # Market appreciation forecast from community sentiment
    market_avg = delta.get("market_prices", {}).get("final_avg", 0)
    appreciation_pct = round(2.0 + market_avg * 3.0, 1)

    # Determine timing action
    if market_trend in ("bearish", "cautiously_bearish"):
        timing_action = "buy_now"
    elif market_trend == "bullish":
        timing_action = "wait_3_months"
    else:
        timing_action = "proceed_cautiously"

    market_data = narratives.get("market_prices", {})
    supportive_count = market_data.get("supportive_count", 0)
    opposed_count = market_data.get("opposed_count", 0)

    asking_price = property_data.get("asking_price", 0)

    monthly_income = cast(float, target_household.monthly_income)
    housing_cost = cast(float, target_household.monthly_housing_cost)
    cost_burden = (
        round(housing_cost / monthly_income * 100, 1)
        if monthly_income > 0
        else 0
    )

    safety_opinion = narratives.get(
        "neighborhood_safety", {},
    ).get("avg_opinion", 0)
    voucher_opinion = narratives.get(
        "voucher_program", {},
    ).get("avg_opinion", 0)
    eviction_opinion = narratives.get(
        "eviction_policy", {},
    ).get("avg_opinion", 0)

    report_json: dict[str, Any] = {
        # Standard MiroFish sections
        "market_outlook": {
            "trend": market_trend,
            "confidence": market_data.get(
                "consensus_strength", 0.5,
            ),
            "market_health_score": health_score,
            "projected_appreciation_pct": appreciation_pct,
            "source": "social_simulation",
            "simulation_run_id": run.id,
        },
        "timing_recommendation": {
            "action": timing_action,
            "reasoning": (
                f"Community sentiment is {market_trend}. "
                f"{supportive_count} households are bullish, "
                f"{opposed_count} are bearish."
            ),
        },
        "strategy_comparison": _derive_strategies(
            run, target_household,
        ),
        "risk_assessment": _extract_risk_narratives(
            run, target_household,
        ),
        "decision_anchors": {
            "max_recommended_price": (
                asking_price * (1.0 + appreciation_pct / 100 * 0.5)
            ),
            "walk_away_price": asking_price * 0.85,
        },
        "monte_carlo_results": {
            "probability_of_loss": _derive_risk(
                run, target_household,
            ),
            "hold_years": 10,
            "mean_irr": round(5.0 + market_avg * 4.0, 1),
            "irr_distribution": {
                "p10": round(1.0 + market_avg * 2.0, 1),
                "p50": round(5.0 + market_avg * 4.0, 1),
                "p90": round(10.0 + market_avg * 5.0, 1),
            },
        },
        "comparable_sales_analysis": {
            "median_price_per_sqft": property_data.get(
                "price_per_sqft", 200,
            ),
            "subject_price_per_sqft": property_data.get(
                "price_per_sqft", 200,
            ),
            "value_indicator": "at_market",
        },
        "neighborhood_scoring": {
            "overall_score": health_score,
            "safety": int(50 + (safety_opinion + 1) * 25),
            "community_support": int(
                50 + (voucher_opinion + 1) * 25,
            ),
            "policy_environment": int(
                50 + (eviction_opinion + 1) * 25,
            ),
        },
        # Social simulation-specific sections
        "household_context": {
            "income_band": cast(str, target_household.income_band),
            "eviction_risk": cast(
                float, target_household.eviction_risk,
            ),
            "voucher_eligible": bool(
                target_household.has_housing_voucher,
            ),
            "housing_cost_burden_pct": cost_burden,
            "peer_sentiment": _get_peer_group_opinion(
                run, target_household,
            ),
            "neighborhood_narrative": narratives.get(
                "neighborhood_safety", {},
            ),
        },
        "community_intelligence": {
            "simulation_run_id": run.id,
            "total_rounds": run.total_rounds,
            "households_simulated": len(
                market_data.get("income_breakdown", {}),
            ),
            "narrative_summary": {
                topic: {
                    "dominant_stance": data.get(
                        "dominant_stance", "divided",
                    ),
                    "consensus_strength": data.get(
                        "consensus_strength", 0,
                    ),
                    "supportive_count": data.get(
                        "supportive_count", 0,
                    ),
                    "opposed_count": data.get("opposed_count", 0),
                }
                for topic, data in narratives.items()
            },
            "sentiment_shifts": delta,
        },
    }

    return report_json


async def generate_report_from_social_sim(
    run_id: str,
    property_id: str,
    household_id: str,
) -> str | None:
    """Create a MiroFishReport from a completed social simulation run.

    Returns the report_id, or None if the run is not completed.
    """
    async with async_session() as db:
        # Load the simulation run
        run_result = await db.execute(
            select(SocialSimulationRun).where(
                SocialSimulationRun.id == run_id,
            )
        )
        run = run_result.scalar_one_or_none()
        if not run or run.status != "completed":
            return None

        # Load target household
        h_result = await db.execute(
            select(HouseholdProfile).where(
                HouseholdProfile.id == household_id,
            )
        )
        household = h_result.scalar_one_or_none()
        if not household:
            return None

        # Load property data
        prop_result = await db.execute(
            select(Property).where(Property.id == property_id)
        )
        prop = prop_result.scalar_one_or_none()

        property_data: dict[str, Any] = {}
        if prop:
            sqft = prop.sqft or 0
            property_data = {
                "asking_price": prop.asking_price,
                "price_per_sqft": (
                    prop.asking_price / sqft if sqft else 200
                ),
                "bedrooms": prop.bedrooms,
                "bathrooms": prop.bathrooms,
                "sqft": sqft,
                "address": prop.address,
            }

        # Build the report
        report_json = build_report_from_social_sim(
            run, household, property_data,
        )

        # Save as MiroFishReport
        report = MiroFishReport(
            user_id=run.trigger_user_id,
            seed_hash=f"social_sim:{run_id}",
            simulation_config={
                "source": "social_simulation",
                "run_id": run_id,
                "household_id": household_id,
                "property_id": property_id,
            },
            report_json=report_json,
            status="completed",
        )
        db.add(report)

        # Link report back to simulation run
        await db.execute(
            update(SocialSimulationRun)
            .where(SocialSimulationRun.id == run_id)
            .values(report_id=report.id)
        )

        await db.commit()
        return cast(str, report.id)
