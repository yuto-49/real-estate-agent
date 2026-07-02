"""Price-vs-probability curve engine.

Given a property's satei value, produces probability-of-closing curves
at different asking prices over 30/60/90/180-day windows.

Uses Monte Carlo sampling over market condition sliders, with each iteration
running a simplified demand model calibrated against historical transaction data.
"""

from __future__ import annotations

import logging
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PriceProbabilityPoint:
    asking_price_yen: int
    premium_pct: float           # asking vs satei, e.g. +5.0
    p30: float                   # P(close within 30 days)
    p60: float
    p90: float
    p180: float
    expected_days: int           # median days to close
    expected_settlement_yen: int # expected final price


@dataclass(frozen=True)
class PriceProbabilityCurve:
    satei_price_yen: int
    points: tuple[PriceProbabilityPoint, ...]
    iterations_per_point: int
    generated_at: datetime = field(default_factory=datetime.utcnow)


def compute_price_probability_curve(
    *,
    satei_price_yen: int,
    range_low_pct: float = -10.0,
    range_high_pct: float = 20.0,
    step_pct: float = 2.0,
    iterations: int = 200,
    seed: int | None = None,
    avg_days_on_market: int = 60,
    demand_elasticity: float = 2.5,
) -> PriceProbabilityCurve:
    """Compute price-vs-probability curve via Monte Carlo.

    The model: for each asking price, we estimate days-to-close as a function
    of the premium over satei. Higher premiums reduce buyer demand, increasing
    time-on-market. Market condition noise is sampled each iteration.

    Parameters
    ----------
    satei_price_yen:
        Fair market value from satei engine.
    range_low_pct, range_high_pct:
        Asking price range as % of satei (e.g. -10 to +20).
    step_pct:
        Step size in percentage points.
    iterations:
        Monte Carlo iterations per price point.
    avg_days_on_market:
        Baseline average days to close at fair value (from REINFOLIB calibration).
    demand_elasticity:
        How sensitive days-to-close is to price premium.
        elasticity=2.5 means +10% premium → +25% more days.
    """
    rng = random.Random(seed)
    points: list[PriceProbabilityPoint] = []

    pct = range_low_pct
    while pct <= range_high_pct + 0.01:
        asking = int(satei_price_yen * (1 + pct / 100))
        days_samples: list[int] = []
        settlement_samples: list[int] = []

        for _ in range(iterations):
            # Market condition noise: ±30% variation in baseline days
            market_factor = rng.uniform(0.7, 1.3)
            # Seasonal noise: ±10%
            seasonal_factor = rng.uniform(0.9, 1.1)

            # Days to close = baseline * (1 + elasticity * premium%)
            premium = pct / 100.0
            demand_penalty = 1.0 + demand_elasticity * max(premium, 0)
            # Below-market pricing accelerates sales (e.g. -10% → 0.7x days)
            demand_bonus = 1.0 + 3.0 * min(premium, 0) if premium < 0 else 1.0

            days = int(
                avg_days_on_market
                * demand_penalty
                * demand_bonus
                * market_factor
                * seasonal_factor
            )
            days = max(days, 7)  # minimum 1 week
            days_samples.append(days)

            # Settlement price: asking price minus negotiation discount
            # Bigger premium → bigger discount as buyer negotiates harder
            discount_pct = rng.uniform(0, min(abs(premium) * 0.5, 0.10))
            settlement = int(asking * (1 - discount_pct))
            settlement_samples.append(settlement)

        # Compute probabilities
        p30 = sum(1 for d in days_samples if d <= 30) / iterations
        p60 = sum(1 for d in days_samples if d <= 60) / iterations
        p90 = sum(1 for d in days_samples if d <= 90) / iterations
        p180 = sum(1 for d in days_samples if d <= 180) / iterations

        points.append(PriceProbabilityPoint(
            asking_price_yen=asking,
            premium_pct=round(pct, 1),
            p30=round(p30, 3),
            p60=round(p60, 3),
            p90=round(p90, 3),
            p180=round(p180, 3),
            expected_days=int(statistics.median(days_samples)),
            expected_settlement_yen=int(statistics.median(settlement_samples)),
        ))

        pct += step_pct

    return PriceProbabilityCurve(
        satei_price_yen=satei_price_yen,
        points=tuple(points),
        iterations_per_point=iterations,
    )
