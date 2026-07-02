from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from domain.reactions.models import ReactionVector
from domain.reports.models import ReplayFrame


@dataclass(frozen=True, slots=True)
class PolicyShock:
    round_num: int
    shock_type: str
    magnitude: float
    label: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PropertyState:
    occupancy_rate: float
    effective_monthly_rent: float
    monthly_opex: float
    annual_noi: float
    dscr: float
    cap_rate: float
    assessed_value: float


@dataclass(frozen=True, slots=True)
class CohortState:
    cohort_label: str
    size: int
    reaction: ReactionVector
    churn_probability: float
    affordability_pressure_avg: float


@dataclass(frozen=True, slots=True)
class InvestorTrace:
    reaction: ReactionVector
    recommendation: str
    recommendation_score: float
    rationale: str


@dataclass(frozen=True, slots=True)
class SimRound:
    round_num: int
    shocks_applied: tuple[PolicyShock, ...]
    property_state: PropertyState
    cohorts: tuple[CohortState, ...]
    investor_trace: InvestorTrace
    replay_frame: ReplayFrame


@dataclass(frozen=True, slots=True)
class SimConfig:
    max_rounds: int = 20
    convergence_threshold: float = 0.02
    shocks: tuple[PolicyShock, ...] = ()
    base_rent_growth_annual: float = 0.01
    base_expense_growth_annual: float = 0.02
    base_appreciation_annual: float = 0.01


@dataclass(frozen=True, slots=True)
class SimSeed:
    initial_property: PropertyState
    initial_cohorts: tuple[CohortState, ...]
    initial_investor: InvestorTrace
    rent_comps_median: float | None = None
    depreciation_annual_shield: float | None = None
    shield_expires_round: int | None = None
    analyst_score: float | None = None


@dataclass(frozen=True, slots=True)
class SimResult:
    config: SimConfig
    seed: SimSeed
    rounds: tuple[SimRound, ...]
    converged: bool
    final_property: PropertyState
    final_investor: InvestorTrace
    final_cohorts: tuple[CohortState, ...]
    converged_at_round: int | None = None
