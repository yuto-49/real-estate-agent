"""Persona analyst council — parallel multi-agent listing review.

Replaces the buyer/seller/broker negotiation pattern. Personas are
*parallel critics of one listing*, not adversaries in a deal. Each persona
issues one Claude call against its scoped prompt and returns a structured
verdict; the council aggregates them and computes a final blended score.

Cost target: ≤5 Claude calls per listing review (4 personas + optional
aggregator). All personas default to Haiku.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import anthropic

from agent.analyst_personas import COUNCIL, AnalystPersona
from config import settings
from db.models import ConstructionType, Property
from intelligence.depreciation_jp import project_depreciation

log = logging.getLogger(__name__)


# ── Result containers ─────────────────────────────────────────────────


@dataclass(frozen=True)
class AnalystVerdict:
    persona_key: str
    persona_title_ja: str
    payload: dict[str, Any]           # raw structured JSON the model returned
    error: str | None = None


@dataclass(frozen=True)
class ListingAnalysis:
    listing_id: str
    verdicts: tuple[AnalystVerdict, ...]
    overall_score: float              # 0-100 blended risk/location score
    summary: str


# ── Context-building helpers ──────────────────────────────────────────


def _serialize_listing(prop: Property) -> dict[str, Any]:
    """Trim a Property row to fields the council needs."""
    return {
        "id": prop.id,
        "address": prop.address,
        "asking_price_yen": (
            int(prop.baibai_kakaku_yen) if prop.baibai_kakaku_yen is not None
            else int(prop.asking_price or 0)
        ),
        "asset_tier": prop.asset_tier.value if prop.asset_tier else None,
        "construction_type": prop.construction_type.value if prop.construction_type else None,
        "seismic_code": prop.seismic_code.value if prop.seismic_code else None,
        "re_buildable": bool(prop.re_buildable) if prop.re_buildable is not None else None,
        "road_frontage_m": prop.road_frontage_m,
        "ward_code": prop.ward_code,
        "walk_minutes_to_station": prop.walk_minutes_to_station,
        "nearest_stations": prop.nearest_stations,
        "built_year": prop.built_year,
        "menseki_m2": prop.menseki_m2,
        "youto_chiiki": prop.youto_chiiki,
        "kenpei_ritsu": prop.kenpei_ritsu,
        "youseki_ritsu": prop.youseki_ritsu,
        "kanrihi_yen": prop.kanrihi_yen,
        "shuuzenzumitatekin_yen": prop.shuuzenzumitatekin_yen,
        "assumed_monthly_rent_yen": prop.assumed_monthly_rent_yen,
        "occupancy_rate": prop.occupancy_rate,
        "hazard_flags": prop.hazard_flags,
    }


def _build_depreciation_context(
    prop: Property,
    *,
    building_basis_yen: float | None,
    building_age_years: int | None,
    marginal_tax_rate: float,
) -> dict[str, Any]:
    """Compute the deterministic depreciation schedule for the strategist persona."""
    if not prop.construction_type or building_basis_yen is None or building_age_years is None:
        return {"available": False, "reason": "missing construction_type or basis or age"}

    schedule = project_depreciation(
        construction=prop.construction_type,
        building_basis_yen=building_basis_yen,
        building_age_years=building_age_years,
        marginal_tax_rate=marginal_tax_rate,
    )
    return {
        "available": True,
        "residual_life_years": schedule.residual_life_years,
        "annual_depreciation_yen": schedule.annual_depreciation_yen,
        "total_shield_yen": schedule.total_shield_yen,
        "shield_expires_year": schedule.shield_expires_year,
        "marginal_tax_rate": schedule.marginal_tax_rate,
    }


# ── Council runner ────────────────────────────────────────────────────


async def _invoke_persona(
    client: anthropic.AsyncAnthropic,
    persona: AnalystPersona,
    user_payload: dict[str, Any],
) -> AnalystVerdict:
    """Single Claude call for one persona. Tolerant of malformed JSON."""
    try:
        message = await client.messages.create(
            model=persona.model,
            max_tokens=800,
            system=persona.system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Listing + context (JSON):\n```json\n"
                        + json.dumps(user_payload, ensure_ascii=False, indent=2)
                        + "\n```\n\nReturn JSON only, no prose outside it."
                    ),
                }
            ],
        )
        raw = "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        ).strip()
        # Tolerate models wrapping JSON in ```json fences
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        payload = json.loads(raw)
        return AnalystVerdict(
            persona_key=persona.key,
            persona_title_ja=persona.title_ja,
            payload=payload,
        )
    except json.JSONDecodeError as exc:
        log.warning("analyst %s returned malformed JSON: %s", persona.key, exc)
        return AnalystVerdict(
            persona_key=persona.key,
            persona_title_ja=persona.title_ja,
            payload={},
            error=f"malformed_json: {exc}",
        )
    except anthropic.APIError as exc:
        log.warning("analyst %s API error: %s", persona.key, exc)
        return AnalystVerdict(
            persona_key=persona.key,
            persona_title_ja=persona.title_ja,
            payload={},
            error=f"api_error: {exc.__class__.__name__}",
        )


def _blend_overall_score(verdicts: tuple[AnalystVerdict, ...]) -> float:
    """Simple weighted blend of the numeric scores the personas emit."""
    weights = {
        "risk_finder": 0.40,        # risk is the dominant gate
        "location_advantage": 0.30,
        "vacancy_demand": 0.20,
        "depreciation_strategist": 0.10,  # qualitative, scaled below
    }
    total_weight = 0.0
    weighted = 0.0
    for verdict in verdicts:
        if verdict.error:
            continue
        w = weights.get(verdict.persona_key, 0.0)
        if w == 0.0:
            continue
        score = _extract_persona_score(verdict)
        if score is None:
            continue
        weighted += score * w
        total_weight += w
    if total_weight == 0:
        return 0.0
    return round(weighted / total_weight, 1)


def _extract_persona_score(verdict: AnalystVerdict) -> float | None:
    """Pull a 0-100 score from a persona's payload, normalizing where needed."""
    p = verdict.payload
    if verdict.persona_key in ("risk_finder", "location_advantage"):
        v = p.get("score")
        return float(v) if isinstance(v, (int, float)) else None
    if verdict.persona_key == "vacancy_demand":
        occ = p.get("occupancy_forecast")
        if isinstance(occ, (int, float)):
            return float(occ) * 100
        return None
    if verdict.persona_key == "depreciation_strategist":
        thesis = p.get("thesis")
        return {
            "aparuto_shield": 75,
            "rc_stability": 65,
            "shield_expired": 30,
            "weak": 20,
        }.get(thesis)
    return None


def _compose_summary(verdicts: tuple[AnalystVerdict, ...]) -> str:
    parts: list[str] = []
    for v in verdicts:
        if v.error:
            parts.append(f"[{v.persona_title_ja}] エラー: {v.error}")
            continue
        s = v.payload.get("summary")
        if isinstance(s, str) and s:
            parts.append(f"[{v.persona_title_ja}] {s}")
    return " / ".join(parts) if parts else "(no verdicts)"


# ── Public entry point ────────────────────────────────────────────────


async def review_listing(
    prop: Property,
    *,
    client: anthropic.AsyncAnthropic | None = None,
    building_basis_yen: float | None = None,
    building_age_years: int | None = None,
    marginal_tax_rate: float = 0.33,
) -> ListingAnalysis:
    """Run the full council against one listing and return aggregated verdicts."""
    api_client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    listing_ctx = _serialize_listing(prop)
    dep_ctx = _build_depreciation_context(
        prop,
        building_basis_yen=building_basis_yen,
        building_age_years=building_age_years,
        marginal_tax_rate=marginal_tax_rate,
    )

    base_payload: dict[str, Any] = {"listing": listing_ctx}

    async def _run(persona: AnalystPersona) -> AnalystVerdict:
        payload = dict(base_payload)
        if persona.key == "depreciation_strategist":
            payload["depreciation_schedule"] = dep_ctx
        return await _invoke_persona(api_client, persona, payload)

    verdicts = tuple(await asyncio.gather(*[_run(p) for p in COUNCIL]))
    overall = _blend_overall_score(verdicts)
    summary = _compose_summary(verdicts)
    return ListingAnalysis(
        listing_id=prop.id,
        verdicts=verdicts,
        overall_score=overall,
        summary=summary,
    )


__all__ = ["AnalystVerdict", "ListingAnalysis", "review_listing"]
