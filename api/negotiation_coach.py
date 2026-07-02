"""Negotiation strategy coach API — broker-facing coaching endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from services.negotiation_coach import (
    ClientProfile,
    CounterpartyProfile,
    run_coaching_session,
)

router = APIRouter()


class ClientProfileRequest(BaseModel):
    role: str = Field(..., pattern="^(seller|buyer)$")
    reservation_price_yen: int
    batna_yen: int | None = None
    motivation: str = "standard"
    experience_level: str = "intermediate"


class CounterpartyProfileRequest(BaseModel):
    archetype: str = "balanced"
    estimated_budget_yen: int | None = None
    motivation: str = "standard"


class CoachingRequest(BaseModel):
    asking_price_yen: int
    client: ClientProfileRequest
    counterparty: CounterpartyProfileRequest | None = None
    property_address: str | None = None
    num_scenarios: int = Field(default=3, ge=1, le=5)
    max_rounds: int = Field(default=8, ge=3, le=20)


class ScenarioResponse(BaseModel):
    scenario_label: str
    opening_price_yen: int
    rounds: int
    settlement_price_yen: int | None = None
    settled: bool
    concession_path: list[int] = []
    zopa_low_yen: int | None = None
    zopa_high_yen: int | None = None


class CoachingResponse(BaseModel):
    property_address: str | None = None
    client_role: str
    recommended_opening_yen: int
    concession_ladder: list[int] = []
    walk_away_yen: int
    zopa_analysis: str
    scenarios: list[ScenarioResponse] = []
    coaching_notes: list[str] = []


@router.post("/session", response_model=CoachingResponse)
async def run_coaching(body: CoachingRequest) -> CoachingResponse:
    """Run negotiation coaching scenarios for a broker."""
    client = ClientProfile(
        role=body.client.role,
        reservation_price_yen=body.client.reservation_price_yen,
        batna_yen=body.client.batna_yen,
        motivation=body.client.motivation,
        experience_level=body.client.experience_level,
    )

    counter_role = "buyer" if body.client.role == "seller" else "seller"
    counterparty = CounterpartyProfile(
        role=counter_role,
        archetype=body.counterparty.archetype if body.counterparty else "balanced",
        estimated_budget_yen=body.counterparty.estimated_budget_yen if body.counterparty else None,
        motivation=body.counterparty.motivation if body.counterparty else "standard",
    )

    result = run_coaching_session(
        asking_price_yen=body.asking_price_yen,
        client=client,
        counterparty=counterparty,
        property_address=body.property_address,
        num_scenarios=body.num_scenarios,
        max_rounds=body.max_rounds,
    )

    return CoachingResponse(
        property_address=result.property_address,
        client_role=result.client_role,
        recommended_opening_yen=result.recommended_opening_yen,
        concession_ladder=list(result.concession_ladder),
        walk_away_yen=result.walk_away_yen,
        zopa_analysis=result.zopa_analysis,
        scenarios=[
            ScenarioResponse(
                scenario_label=s.scenario_label,
                opening_price_yen=s.opening_price_yen,
                rounds=s.rounds,
                settlement_price_yen=s.settlement_price_yen,
                settled=s.settled,
                concession_path=list(s.concession_path),
                zopa_low_yen=s.zopa_low_yen,
                zopa_high_yen=s.zopa_high_yen,
            )
            for s in result.scenarios
        ],
        coaching_notes=list(result.coaching_notes),
    )
