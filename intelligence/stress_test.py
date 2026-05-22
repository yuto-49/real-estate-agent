"""Monte Carlo stress-test for property underwriting.

Samples 5 sliders uniformly across user-specified ranges, runs the underwriting
engine N times, and reports the distribution + a tornado decomposition.

Determinism: pass ``seed`` to make runs reproducible.

The 5 sliders:
1. ``vacancy_rate`` — fraction of rent lost to vacancy
2. ``rent_growth`` — annual rent escalation
3. ``expense_growth`` — annual opex escalation
4. ``loan_rate`` — mortgage rate (re-amortizes the deal)
5. ``exit_cap_rate`` — cap rate applied to terminal NOI for IRR
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field, replace
from typing import Iterable

from intelligence.underwriting import (
    UnderwritingInputs,
    UnderwritingResult,
    underwrite,
)


@dataclass(frozen=True, slots=True)
class SliderRange:
    low: float
    high: float

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError("SliderRange.high must be >= low")

    def sample(self, rng: random.Random) -> float:
        return rng.uniform(self.low, self.high)

    def midpoint(self) -> float:
        return (self.low + self.high) / 2.0


@dataclass(frozen=True, slots=True)
class StressTestConfig:
    iterations: int = 5000
    vacancy_rate: SliderRange = SliderRange(0.03, 0.12)
    rent_growth: SliderRange = SliderRange(0.0, 0.04)
    expense_growth: SliderRange = SliderRange(0.02, 0.04)
    loan_rate: SliderRange = SliderRange(0.05, 0.08)
    exit_cap_rate: SliderRange = SliderRange(0.06, 0.085)
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class StressTestResult:
    iterations: int
    cap_rate_p10: float
    cap_rate_p50: float
    cap_rate_p90: float
    cash_on_cash_p10: float
    cash_on_cash_p50: float
    cash_on_cash_p90: float
    dscr_p10: float
    dscr_p50: float
    dscr_p90: float
    irr_5yr_p10: float | None
    irr_5yr_p50: float | None
    irr_5yr_p90: float | None
    probability_negative_cash_flow: float
    probability_dscr_under_1: float
    tornado: dict
    irr_5yr_samples: tuple[float, ...] = field(default_factory=tuple)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = int(round((len(s) - 1) * q))
    return s[k]


def _percentile_optional(values: list[float | None], q: float) -> float | None:
    filtered = [v for v in values if v is not None]
    return _percentile(filtered, q) if filtered else None


def _sample_inputs(
    base: UnderwritingInputs, config: StressTestConfig, rng: random.Random
) -> UnderwritingInputs:
    return replace(
        base,
        vacancy_rate=config.vacancy_rate.sample(rng),
        rent_growth=config.rent_growth.sample(rng),
        expense_growth=config.expense_growth.sample(rng),
        loan_rate=config.loan_rate.sample(rng),
        exit_cap_rate=config.exit_cap_rate.sample(rng),
    )


def monte_carlo_stress_test(
    base: UnderwritingInputs, config: StressTestConfig
) -> StressTestResult:
    """Run a Monte Carlo stress test on a single property's underwriting."""
    rng = random.Random(config.seed)

    cap_rates: list[float] = []
    cocs: list[float] = []
    dscrs: list[float] = []
    irr_5s: list[float | None] = []
    negative_cf = 0
    dscr_under_1 = 0

    for _ in range(config.iterations):
        sampled = _sample_inputs(base, config, rng)
        r = underwrite(sampled)
        cap_rates.append(r.cap_rate)
        cocs.append(r.cash_on_cash)
        # Treat infinite DSCR (no loan) as a very large number for stats
        dscrs.append(min(r.dscr, 99.0) if r.dscr != float("inf") else 99.0)
        irr_5s.append(r.irr_5yr)
        if r.cash_on_cash < 0:
            negative_cf += 1
        if r.dscr < 1.0:
            dscr_under_1 += 1

    tornado = _tornado(base, config)

    irr_5_clean = tuple(v for v in irr_5s if v is not None)

    return StressTestResult(
        iterations=config.iterations,
        cap_rate_p10=_percentile(cap_rates, 0.10),
        cap_rate_p50=_percentile(cap_rates, 0.50),
        cap_rate_p90=_percentile(cap_rates, 0.90),
        cash_on_cash_p10=_percentile(cocs, 0.10),
        cash_on_cash_p50=_percentile(cocs, 0.50),
        cash_on_cash_p90=_percentile(cocs, 0.90),
        dscr_p10=_percentile(dscrs, 0.10),
        dscr_p50=_percentile(dscrs, 0.50),
        dscr_p90=_percentile(dscrs, 0.90),
        irr_5yr_p10=_percentile_optional(irr_5s, 0.10),
        irr_5yr_p50=_percentile_optional(irr_5s, 0.50),
        irr_5yr_p90=_percentile_optional(irr_5s, 0.90),
        probability_negative_cash_flow=negative_cf / max(config.iterations, 1),
        probability_dscr_under_1=dscr_under_1 / max(config.iterations, 1),
        tornado=tornado,
        irr_5yr_samples=irr_5_clean,
    )


def _tornado(base: UnderwritingInputs, config: StressTestConfig) -> dict:
    """Per-variable swing in cash-on-cash (held everything else at midpoint)."""
    mids = {
        "vacancy_rate": config.vacancy_rate.midpoint(),
        "rent_growth": config.rent_growth.midpoint(),
        "expense_growth": config.expense_growth.midpoint(),
        "loan_rate": config.loan_rate.midpoint(),
        "exit_cap_rate": config.exit_cap_rate.midpoint(),
    }
    out: dict = {}
    for name, slider in [
        ("vacancy_rate", config.vacancy_rate),
        ("rent_growth", config.rent_growth),
        ("expense_growth", config.expense_growth),
        ("loan_rate", config.loan_rate),
        ("exit_cap_rate", config.exit_cap_rate),
    ]:
        low_inputs = replace(base, **{**mids, name: slider.low})
        high_inputs = replace(base, **{**mids, name: slider.high})
        low_r = underwrite(low_inputs)
        high_r = underwrite(high_inputs)
        swing = abs(high_r.cash_on_cash - low_r.cash_on_cash)
        out[name] = {
            "low_coc": low_r.cash_on_cash,
            "high_coc": high_r.cash_on_cash,
            "swing": swing,
        }
    return out


__all__ = [
    "SliderRange",
    "StressTestConfig",
    "StressTestResult",
    "monte_carlo_stress_test",
]
