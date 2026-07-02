"""Market-wide investor simulation API.

Implements the 6 endpoints consumed by MarketSimulationWorkspace:
  POST /market/personas     — generate synthetic investor personas
  POST /market/start        — launch a tick-based market simulation
  GET  /market/status/{id}  — poll run progress
  GET  /market/result/{id}  — final result summary
  GET  /market/replay/{id}  — full tick-by-tick replay
  POST /market/handoff-to-negotiation — bridge to negotiation engine

The simulation engine runs in-memory using asyncio.Lock for state.
Properties are loaded from the DB (Tokyo inventory).  Investor behaviour
is generated deterministically from persona archetypes + signal weights.
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    InvestorDecisionTrace,
    InvestorTickState,
    MarketInvestorPersona,
    MarketSimulationAcquisition,
    MarketSimulationHandoffRequest,
    MarketSimulationHandoffResponse,
    MarketSimulationInvestorOutcomeSummary,
    MarketSimulationInvestorResponse,
    MarketSimulationPersonaRequest,
    MarketSimulationPersonaResponse,
    MarketSimulationReplayResponse,
    MarketSimulationResultResponse,
    MarketSimulationStartRequest,
    MarketSimulationStartResponse,
    MarketSimulationStatusResponse,
    PropertyTickState,
)
from db.database import get_db
from db.models import Property, PropertyStatus

router = APIRouter()

# ── In-memory store ───────────────────────────────────────────────────────

_store: dict[str, dict[str, Any]] = {}
_lock = asyncio.Lock()

# ── Archetype templates ───────────────────────────────────────────────────

_ARCHETYPE_TEMPLATES: dict[str, dict[str, Any]] = {
    "value": {
        "risk_posture": "Conservative",
        "hold_horizon": "7-10 years",
        "target_yield": "5-7% cap",
        "competition_style": "Patient stalker",
        "exit_style": "Hold until peak valuation",
        "signal_weights": {
            "valuation": 0.35, "yield": 0.25, "neighborhood": 0.15,
            "momentum": 0.05, "risk_penalty": 0.20,
        },
    },
    "yield": {
        "risk_posture": "Moderate",
        "hold_horizon": "5-7 years",
        "target_yield": "6-9% cash-on-cash",
        "competition_style": "Steady accumulator",
        "exit_style": "Sell when yield compresses below target",
        "signal_weights": {
            "valuation": 0.15, "yield": 0.40, "neighborhood": 0.15,
            "momentum": 0.10, "risk_penalty": 0.20,
        },
    },
    "momentum": {
        "risk_posture": "Aggressive",
        "hold_horizon": "2-4 years",
        "target_yield": "Appreciation-driven",
        "competition_style": "First-mover bidder",
        "exit_style": "Flip at attention peak",
        "signal_weights": {
            "valuation": 0.10, "yield": 0.10, "neighborhood": 0.15,
            "momentum": 0.45, "risk_penalty": 0.20,
        },
    },
    "contrarian": {
        "risk_posture": "Opportunistic",
        "hold_horizon": "5-8 years",
        "target_yield": "Deep discount to intrinsic",
        "competition_style": "Counter-cycle buyer",
        "exit_style": "Exit when market normalizes",
        "signal_weights": {
            "valuation": 0.40, "yield": 0.20, "neighborhood": 0.10,
            "momentum": -0.10, "risk_penalty": 0.20,
        },
    },
}

_COHORT_PRESETS: dict[str, list[str]] = {
    "balanced": ["value", "yield", "momentum", "contrarian"],
    "income": ["yield", "yield", "value", "contrarian"],
    "momentum": ["momentum", "momentum", "value", "yield"],
}

_NAMES = [
    "Tanaka Capital", "Suzuki Realty", "Sato Holdings", "Yamamoto Fund",
    "Watanabe Inv", "Ito Partners", "Nakamura RE", "Kobayashi Group",
    "Kato Trust", "Yoshida Asset", "Yamada Equity", "Sasaki Ventures",
    "Matsumoto Cap", "Inoue Fund", "Kimura Inv", "Hayashi RE",
    "Shimizu Group", "Yamaguchi Trust", "Mori Partners", "Abe Capital",
    "Ikeda Holdings", "Hashimoto Fund", "Ishikawa RE", "Ogawa Group",
    "Maeda Inv", "Fujita Asset", "Okada Capital", "Goto Ventures",
    "Hasegawa Eq", "Murakami Trust", "Kondo Partners", "Ishii Holdings",
    "Sakamoto Fund", "Endo RE", "Aoki Group", "Fujii Inv",
    "Nishimura Cap", "Fukuda Asset", "Miura Trust", "Takeuchi Realty",
]

_TOKYO_NEIGHBORHOODS = [
    "Minato-ku", "Shibuya-ku", "Shinjuku-ku", "Chiyoda-ku",
    "Setagaya-ku", "Meguro-ku", "Bunkyo-ku", "Toshima-ku",
    "Suginami-ku", "Itabashi-ku", "Nerima-ku", "Koto-ku",
]


# ── Helpers ───────────────────────────────────────────────────────────────

def _deterministic_seed(run_id: str, tick: int, investor_idx: int) -> int:
    h = hashlib.md5(f"{run_id}-{tick}-{investor_idx}".encode()).hexdigest()
    return int(h[:8], 16)


def _build_persona(
    index: int, archetype: str, budget_range: tuple[float, float],
) -> MarketInvestorPersona:
    tpl = _ARCHETYPE_TEMPLATES.get(archetype, _ARCHETYPE_TEMPLATES["value"])
    rng = random.Random(index * 31 + hash(archetype))
    budget = rng.uniform(budget_range[0], budget_range[1])
    name = _NAMES[index % len(_NAMES)]
    neighborhoods = rng.sample(
        _TOKYO_NEIGHBORHOODS, min(3, len(_TOKYO_NEIGHBORHOODS)),
    )
    return MarketInvestorPersona(
        display_name=name,
        archetype=archetype,
        budget=round(budget),
        risk_posture=tpl["risk_posture"],
        hold_horizon=tpl["hold_horizon"],
        target_yield=tpl["target_yield"],
        preferred_property_types=["RC", "SRC", "apartment"],
        preferred_price_band=f"{budget_range[0] / 1e6:.0f}M-{budget_range[1] / 1e6:.0f}M",
        neighborhood_preferences=neighborhoods,
        avoidance_triggers=[
            "high flood risk", "no road frontage", "non-rebuildable",
        ],
        competition_style=tpl["competition_style"],
        exit_style=tpl["exit_style"],
        investment_thesis=(
            f"{archetype.title()} investor targeting Tokyo workforce housing "
            f"with {tpl['target_yield']} returns over a {tpl['hold_horizon']} horizon."
        ),
    )


async def _load_properties(db: AsyncSession, scope: Any) -> list[dict]:
    stmt = select(Property).where(Property.status == PropertyStatus.ACTIVE)
    if scope.property_ids:
        stmt = stmt.where(Property.id.in_(scope.property_ids))
    if scope.property_types:
        stmt = stmt.where(Property.property_type.in_(scope.property_types))
    if scope.min_price is not None:
        stmt = stmt.where(Property.asking_price >= scope.min_price)
    if scope.max_price is not None:
        stmt = stmt.where(Property.asking_price <= scope.max_price)
    stmt = stmt.order_by(Property.asking_price.desc()).limit(50)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "address": p.address,
            "asking_price": float(p.asking_price or 0),
            "latitude": p.latitude,
            "longitude": p.longitude,
            "property_type": p.property_type,
        }
        for p in rows
    ]


def _simulate_tick(
    run_id: str,
    tick_num: int,
    properties: list[dict],
    investors: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """One tick of the market simulation.

    Returns (property_states, decisions, new_acquisitions).
    """
    prop_states: list[dict] = []
    decisions: list[dict] = []
    new_acquisitions: list[dict] = []

    for pi, prop in enumerate(properties):
        if prop.get("_acquired"):
            continue

        reservation = prop["asking_price"] * 0.95
        attention = 0
        bids: list[tuple[int, float, float]] = []

        for ii, inv in enumerate(investors):
            if inv["cash_remaining"] <= 0:
                continue

            rng = random.Random(
                _deterministic_seed(run_id, tick_num, ii * 100 + pi),
            )
            weights = inv["signal_weights"]

            price_ratio = prop["asking_price"] / max(inv["budget"], 1)
            valuation_score = max(0, 1 - price_ratio) * weights.get("valuation", 0.2)
            yield_score = rng.uniform(0.3, 0.8) * weights.get("yield", 0.2)
            neighborhood_score = rng.uniform(0.2, 0.7) * weights.get("neighborhood", 0.15)
            momentum_val = weights.get("momentum", 0.1)
            momentum_score = (tick_num / 10) * rng.uniform(0.1, 0.6) * abs(momentum_val)
            if momentum_val < 0:
                momentum_score = -momentum_score
            risk_penalty = rng.uniform(0.05, 0.3) * weights.get("risk_penalty", 0.2)
            total_score = (
                valuation_score + yield_score + neighborhood_score
                + momentum_score - risk_penalty
            )

            affordable = inv["cash_remaining"] >= prop["asking_price"] * 0.2
            if not affordable:
                action = "skip"
            elif total_score > 0.5 + (tick_num * 0.02):
                action = "enter" if rng.random() < 0.6 else "raise_bid"
                bid = prop["asking_price"] * rng.uniform(0.88, 1.02)
                bids.append((ii, bid, total_score))
                attention += 1
            elif total_score > 0.3:
                action = "watch"
                attention += 1
            else:
                action = "skip"

            if action != "skip":
                decisions.append({
                    "investor_id": inv["id"],
                    "investor_name": inv["name"],
                    "archetype": inv["archetype"],
                    "tick_num": tick_num,
                    "property_id": prop["id"],
                    "property_address": prop["address"],
                    "chosen_action": action,
                    "bid_amount": (
                        bids[-1][1] if bids and bids[-1][0] == ii else None
                    ),
                    "total_score": round(total_score, 4),
                    "signal_scores": {
                        "valuation": round(valuation_score, 4),
                        "yield": round(yield_score, 4),
                        "neighborhood": round(neighborhood_score, 4),
                        "momentum": round(momentum_score, 4),
                        "risk_penalty": round(risk_penalty, 4),
                    },
                    "persona_weights": inv["signal_weights"],
                    "peer_inputs": {
                        "attention": attention, "bid_count": len(bids),
                    },
                    "property_match_factors": [
                        "Tokyo workforce housing",
                        f"price ratio {price_ratio:.2f}",
                    ],
                    "budget_position": {
                        "cash_remaining": inv["cash_remaining"],
                        "asking_price": prop["asking_price"],
                        "headroom": inv["cash_remaining"] - prop["asking_price"] * 0.2,
                        "is_affordable": affordable,
                    },
                    "persona_summary": {},
                    "chosen_action_reason": (
                        f"{inv['archetype'].title()} scored "
                        f"{total_score:.2f} on this property."
                    ),
                    "entry_or_exit_reason": (
                        f"{'Entered' if action in ('enter', 'raise_bid') else 'Watching'} "
                        f"based on {inv['archetype']} strategy."
                    ),
                    "rejected_alternatives": [],
                })

        # Check for acquisition
        winning_investor_id = None
        if bids:
            bids.sort(key=lambda b: b[2], reverse=True)
            top_ii, top_bid, top_score = bids[0]
            if top_bid >= reservation and top_score > 0.55:
                winning_investor_id = investors[top_ii]["id"]
                prop["_acquired"] = True
                investors[top_ii]["cash_remaining"] -= top_bid * 0.2
                investors[top_ii]["holdings"].append(prop["id"])
                new_acquisitions.append({
                    "property_id": prop["id"],
                    "property_address": prop["address"],
                    "winning_investor_id": winning_investor_id,
                    "winning_investor_name": investors[top_ii]["name"],
                    "acquired_tick": tick_num,
                    "winning_bid": round(top_bid),
                })

        prop_states.append({
            "property_id": prop["id"],
            "address": prop["address"],
            "latitude": prop.get("latitude"),
            "longitude": prop.get("longitude"),
            "asking_price": prop["asking_price"],
            "property_type": prop.get("property_type"),
            "tick_num": tick_num,
            "status": "acquired" if prop.get("_acquired") else "active",
            "attention_count": attention,
            "bid_count": len(bids),
            "top_bid": max((b[1] for b in bids), default=None),
            "bid_velocity": len(bids) * 0.1,
            "local_competition": attention * 0.15,
            "recent_attention": float(attention),
            "reservation_threshold": reservation,
            "winning_investor_id": winning_investor_id,
            "signal_snapshot": {},
            "targeted_investor_ids": [str(bids[i][0]) for i in range(len(bids))],
        })

    return prop_states, decisions, new_acquisitions


def _build_investor_response(inv: dict) -> MarketSimulationInvestorResponse:
    return MarketSimulationInvestorResponse(
        id=inv["id"],
        investor_name=inv["name"],
        archetype=inv["archetype"],
        budget=inv["budget"],
        cash_remaining=inv["cash_remaining"],
        hold_horizon_ticks=inv["hold_horizon_ticks"],
        risk_appetite=inv["risk_appetite"],
        diversification_cap=inv["diversification_cap"],
        preferred_property_types=inv["preferred_property_types"],
        signal_weights=inv["signal_weights"],
        holdings=inv["holdings"],
        persona=(
            MarketInvestorPersona(**inv["persona"])
            if inv.get("persona") else None
        ),
        outcome_summary=MarketSimulationInvestorOutcomeSummary(
            **inv.get("outcome_summary", {}),
        ),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/market/personas", response_model=MarketSimulationPersonaResponse)
async def generate_personas(
    req: MarketSimulationPersonaRequest,
    db: AsyncSession = Depends(get_db),
):
    props = await _load_properties(db, req.scope)
    if not props:
        return MarketSimulationPersonaResponse(
            property_count=0,
            personas=[],
            inventory_summary={"warning": "No active properties found"},
        )

    prices = [p["asking_price"] for p in props]
    budget_lo = min(prices) * 0.5
    budget_hi = max(prices) * 1.5
    archetypes = _COHORT_PRESETS.get(
        req.cohort_preset, _COHORT_PRESETS["balanced"],
    )
    personas = [
        _build_persona(i, archetypes[i % len(archetypes)], (budget_lo, budget_hi))
        for i in range(req.investor_count)
    ]

    return MarketSimulationPersonaResponse(
        property_count=len(props),
        personas=personas,
        inventory_summary={
            "property_count": len(props),
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) / len(prices),
            "types": list({p.get("property_type") or "unknown" for p in props}),
        },
    )


@router.post("/market/start", response_model=MarketSimulationStartResponse)
async def start_market_simulation(
    req: MarketSimulationStartRequest,
    db: AsyncSession = Depends(get_db),
):
    props = await _load_properties(db, req.scope)
    if not props:
        raise HTTPException(
            status_code=400, detail="No active properties match the scope",
        )

    run_id = str(uuid.uuid4())
    prices = [p["asking_price"] for p in props]
    budget_lo = min(prices) * 0.5
    budget_hi = max(prices) * 1.5
    archetypes = _COHORT_PRESETS.get(
        req.cohort_preset, _COHORT_PRESETS["balanced"],
    )

    investors: list[dict[str, Any]] = []
    for i in range(req.investor_count):
        if req.seeded_personas and i < len(req.seeded_personas):
            arch = req.seeded_personas[i].archetype
        else:
            arch = archetypes[i % len(archetypes)]
        tpl = _ARCHETYPE_TEMPLATES.get(arch, _ARCHETYPE_TEMPLATES["value"])
        rng = random.Random(i * 37 + hash(run_id))
        budget = rng.uniform(budget_lo, budget_hi)
        investors.append({
            "id": str(uuid.uuid4()),
            "name": (
                req.seeded_personas[i].display_name
                if req.seeded_personas and i < len(req.seeded_personas)
                else _NAMES[i % len(_NAMES)]
            ),
            "archetype": arch,
            "budget": round(budget),
            "cash_remaining": round(budget),
            "hold_horizon_ticks": rng.randint(4, 15),
            "risk_appetite": round(rng.uniform(0.3, 0.9), 2),
            "diversification_cap": rng.randint(2, 5),
            "preferred_property_types": ["RC", "SRC", "apartment"],
            "signal_weights": tpl["signal_weights"],
            "holdings": [],
            "persona": (
                req.seeded_personas[i].model_dump()
                if req.seeded_personas and i < len(req.seeded_personas)
                else None
            ),
        })

    # Run simulation (fast for <=50 props x <=40 investors x <=20 ticks)
    all_ticks: list[dict] = []
    all_acquisitions: list[dict] = []
    working_props = [dict(p) for p in props]

    for tick in range(1, req.tick_count + 1):
        pstates, tdecisions, tacqs = _simulate_tick(
            run_id, tick, working_props, investors,
        )
        all_ticks.append({
            "tick_number": tick,
            "property_states": pstates,
            "decisions": tdecisions,
        })
        all_acquisitions.extend(tacqs)

    # Build outcome summaries
    for inv in investors:
        inv_decisions = [
            d for t in all_ticks for d in t["decisions"]
            if d["investor_id"] == inv["id"]
        ]
        inv["outcome_summary"] = {
            "decisions_made": len(inv_decisions),
            "watch_actions": sum(
                1 for d in inv_decisions if d["chosen_action"] == "watch"
            ),
            "bid_actions": sum(
                1 for d in inv_decisions
                if d["chosen_action"] in ("enter", "raise_bid")
            ),
            "acquisitions": len(inv["holdings"]),
            "last_action": (
                inv_decisions[-1]["chosen_action"] if inv_decisions else None
            ),
            "last_property_id": (
                inv_decisions[-1]["property_id"] if inv_decisions else None
            ),
            "last_property_address": (
                inv_decisions[-1]["property_address"] if inv_decisions else None
            ),
        }

    now = datetime.now(timezone.utc)
    async with _lock:
        _store[run_id] = {
            "status": "completed",
            "run_label": req.run_label,
            "investor_count": req.investor_count,
            "property_count": len(props),
            "total_ticks": req.tick_count,
            "completed_ticks": req.tick_count,
            "investors": investors,
            "ticks": all_ticks,
            "acquisitions": all_acquisitions,
            "created_at": now,
            "completed_at": now,
        }

    return MarketSimulationStartResponse(
        run_id=run_id, status="completed", message="Simulation completed",
    )


@router.get(
    "/market/status/{run_id}",
    response_model=MarketSimulationStatusResponse,
)
async def get_market_status(run_id: str):
    async with _lock:
        run = _store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return MarketSimulationStatusResponse(
        run_id=run_id,
        status=run["status"],
        current_tick=run["completed_ticks"],
        total_ticks=run["total_ticks"],
        progress=100 if run["status"] == "completed" else 0,
        investor_count=run["investor_count"],
        property_count=run["property_count"],
        run_label=run.get("run_label"),
        created_at=run.get("created_at"),
        completed_at=run.get("completed_at"),
    )


@router.get(
    "/market/result/{run_id}",
    response_model=MarketSimulationResultResponse,
)
async def get_market_result(run_id: str):
    async with _lock:
        run = _store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    total_decisions = sum(len(t["decisions"]) for t in run["ticks"])
    return MarketSimulationResultResponse(
        run_id=run_id,
        status=run["status"],
        total_ticks=run["total_ticks"],
        completed_ticks=run["completed_ticks"],
        summary={
            "decision_count": total_decisions,
            "acquisition_count": len(run["acquisitions"]),
            "market_temperature": min(
                1.0,
                len(run["acquisitions"]) / max(run["property_count"], 1),
            ),
        },
        acquisitions=[
            MarketSimulationAcquisition(**a) for a in run["acquisitions"]
        ],
        investors=[_build_investor_response(inv) for inv in run["investors"]],
    )


@router.get(
    "/market/replay/{run_id}",
    response_model=MarketSimulationReplayResponse,
)
async def get_market_replay(run_id: str):
    async with _lock:
        run = _store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    total_decisions = sum(len(t["decisions"]) for t in run["ticks"])
    return MarketSimulationReplayResponse(
        run_id=run_id,
        status=run["status"],
        run_label=run.get("run_label"),
        total_ticks=run["total_ticks"],
        completed_ticks=run["completed_ticks"],
        investors=[_build_investor_response(inv) for inv in run["investors"]],
        ticks=[
            InvestorTickState(
                tick_number=t["tick_number"],
                property_states=[
                    PropertyTickState(**ps) for ps in t["property_states"]
                ],
                decisions=[
                    InvestorDecisionTrace(**d) for d in t["decisions"]
                ],
            )
            for t in run["ticks"]
        ],
        summary={
            "decision_count": total_decisions,
            "acquisition_count": len(run["acquisitions"]),
            "market_temperature": min(
                1.0,
                len(run["acquisitions"]) / max(run["property_count"], 1),
            ),
        },
    )


@router.post(
    "/market/handoff-to-negotiation",
    response_model=MarketSimulationHandoffResponse,
)
async def handoff_to_negotiation(req: MarketSimulationHandoffRequest):
    async with _lock:
        run = _store.get(req.run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    investor = next(
        (i for i in run["investors"] if i["id"] == req.investor_id), None,
    )
    if not investor:
        raise HTTPException(
            status_code=404, detail="Investor not found in this run",
        )

    return MarketSimulationHandoffResponse(
        simulation_id=str(uuid.uuid4()),
        status="created",
        investor_id=req.investor_id,
        property_id=req.property_id,
        seeded_config={
            "archetype": investor["archetype"],
            "budget": investor["budget"],
            "signal_weights": investor["signal_weights"],
        },
        message=f"Negotiation seeded from market simulation for {investor['name']}",
    )
