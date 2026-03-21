"""MiroFish Client — programmatic interface to the simulation engine.

Includes tenacity exponential backoff + jitter, circuit breaker pattern,
separate submit/poll API for async workflows, and a mock client for
local simulation mode.
"""

import asyncio
import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

from config import settings
from services.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MiroFishReportData:
    # Existing fields
    market_outlook: dict = field(default_factory=dict)
    timing_recommendation: dict = field(default_factory=dict)
    strategy_comparison: list = field(default_factory=list)
    risk_assessment: list = field(default_factory=list)
    property_recommendations: list = field(default_factory=list)
    decision_anchors: dict = field(default_factory=dict)
    raw_json: dict = field(default_factory=dict)

    # NEW — Deep financial analysis fields
    financial_analysis: dict = field(default_factory=dict)
    monte_carlo_results: dict = field(default_factory=dict)
    cash_flow_projections: dict = field(default_factory=dict)
    rent_vs_buy_analysis: dict = field(default_factory=dict)
    tax_benefit_estimation: dict = field(default_factory=dict)
    portfolio_metrics: dict = field(default_factory=dict)
    comparable_sales_analysis: dict = field(default_factory=dict)
    neighborhood_scoring: dict = field(default_factory=dict)


class CircuitBreaker:
    """Simple circuit breaker: opens after N consecutive failures."""

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._state = "closed"  # closed, open, half_open
        self._last_failure_time: float = 0

    def record_success(self):
        self._failures = 0
        self._state = "closed"

    def record_failure(self):
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = "open"
            import time
            self._last_failure_time = time.monotonic()

    @property
    def is_open(self) -> bool:
        if self._state == "open":
            import time
            if time.monotonic() - self._last_failure_time > self.reset_timeout:
                self._state = "half_open"
                return False
            return True
        return False

    def check(self):
        if self.is_open:
            raise CircuitBreakerOpen("Circuit breaker is open — MiroFish unavailable")


class CircuitBreakerOpen(Exception):
    pass


class MiroFishClient:
    """HTTP client to the MiroFish simulation backend."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.mirofish_api_url
        self.http = httpx.AsyncClient(base_url=self.base_url, timeout=600.0)
        self.circuit_breaker = CircuitBreaker()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    )
    async def run_simulation(
        self,
        seed_document: str,
        question: str,
        ticks: int = 30,
    ) -> MiroFishReportData:
        """Trigger a synchronous MiroFish simulation and return the structured report."""
        self.circuit_breaker.check()

        try:
            resp = await self.http.post(
                "/api/simulate",
                json={"seed": seed_document, "question": question, "ticks": ticks},
            )
            resp.raise_for_status()
            data = resp.json()
            self.circuit_breaker.record_success()

            return MiroFishReportData(
                market_outlook=data.get("market_outlook", {}),
                timing_recommendation=data.get("timing_recommendation", {}),
                strategy_comparison=data.get("strategy_comparison", []),
                risk_assessment=data.get("risk_assessment", []),
                property_recommendations=data.get("property_recommendations", []),
                decision_anchors=data.get("decision_anchors", {}),
                financial_analysis=data.get("financial_analysis", {}),
                monte_carlo_results=data.get("monte_carlo_results", {}),
                cash_flow_projections=data.get("cash_flow_projections", {}),
                rent_vs_buy_analysis=data.get("rent_vs_buy_analysis", {}),
                tax_benefit_estimation=data.get("tax_benefit_estimation", {}),
                portfolio_metrics=data.get("portfolio_metrics", {}),
                comparable_sales_analysis=data.get("comparable_sales_analysis", {}),
                neighborhood_scoring=data.get("neighborhood_scoring", {}),
                raw_json=data,
            )
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    )
    async def submit_simulation(
        self,
        seed_document: str,
        question: str,
        ticks: int = 30,
        webhook_url: str | None = None,
    ) -> str:
        """Submit a simulation job and return the job ID (async workflow)."""
        self.circuit_breaker.check()

        try:
            payload = {"seed": seed_document, "question": question, "ticks": ticks}
            if webhook_url:
                payload["webhook_url"] = webhook_url
            resp = await self.http.post("/api/simulate/async", json=payload)
            resp.raise_for_status()
            data = resp.json()
            self.circuit_breaker.record_success()
            return data.get("job_id", "")
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=15),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    async def poll_result(self, job_id: str) -> dict:
        """Poll for a simulation result by job ID."""
        resp = await self.http.get(f"/api/simulate/{job_id}")
        resp.raise_for_status()
        return resp.json()

    async def health_check(self) -> bool:
        """Check if MiroFish backend is reachable."""
        try:
            resp = await self.http.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.http.aclose()


class MockMiroFishClient:
    """Local simulation client that generates deep investment analysis
    using actual financial models. Used in simulation mode."""

    def __init__(self):
        self._rng = random.Random()

    async def health_check(self) -> bool:
        return True

    async def run_simulation(
        self,
        seed_document: str,
        question: str,
        ticks: int = 30,
    ) -> MiroFishReportData:
        """Generate a deep MiroFish report with tick-based phased computation."""
        from intelligence.financial_models import (
            MortgageCalculator,
            CashFlowModel,
            InvestmentMetrics,
            MonteCarloEngine,
            TaxEstimator,
            PortfolioMetrics,
        )

        # Use seed hash for deterministic but varied results
        seed_hash = hashlib.sha256(seed_document.encode()).hexdigest()
        self._rng.seed(seed_hash)

        # Simulate processing time proportional to ticks
        await asyncio.sleep(min(ticks * 0.05, 2.0))

        # Extract budget hints from seed for realistic output
        budget_max = self._extract_budget(seed_document)
        property_value = int(budget_max * self._rng.uniform(0.75, 0.95))
        appreciation = round(self._rng.uniform(2.0, 7.5), 1)
        market_score = round(self._rng.uniform(55, 92), 1)

        # ── Phase 1 (ticks 1-5): Base Financials ──
        annual_rate = round(self._rng.uniform(0.055, 0.075), 4)
        down_payment_pct = self._rng.choice([0.10, 0.15, 0.20, 0.25])
        loan_amount = property_value * (1 - down_payment_pct)
        loan_years = 30

        monthly_mortgage = MortgageCalculator.monthly_payment(
            loan_amount, annual_rate, loan_years
        )
        total_interest = MortgageCalculator.total_interest(
            loan_amount, annual_rate, loan_years
        )
        amortization = MortgageCalculator.amortization_schedule(
            loan_amount, annual_rate, loan_years
        )

        # Amortization summary (key years)
        amort_summary = {}
        for entry in amortization:
            if entry["year"] in [1, 5, 10, 15, 30]:
                amort_summary[f"year_{entry['year']}_equity_pct"] = entry["equity_pct"]
                amort_summary[f"year_{entry['year']}_balance"] = entry["remaining_balance"]

        monthly_rent = int(property_value * self._rng.uniform(0.005, 0.008))
        monthly_taxes = round(property_value * self._rng.uniform(0.008, 0.025) / 12, 2)
        monthly_insurance = round(self._rng.uniform(100, 250), 2)
        monthly_hoa = round(self._rng.uniform(0, 400), 2)
        vacancy_rate = round(self._rng.uniform(0.03, 0.10), 3)
        maintenance_pct = round(self._rng.uniform(0.008, 0.02), 4)

        cash_flow = CashFlowModel.monthly_cash_flow(
            rental_income=monthly_rent,
            mortgage=monthly_mortgage,
            taxes=monthly_taxes,
            insurance=monthly_insurance,
            hoa=monthly_hoa,
            maintenance_pct=maintenance_pct,
            property_value=property_value,
            vacancy_rate=vacancy_rate,
        )

        financial_analysis = {
            "property_value": property_value,
            "down_payment_pct": down_payment_pct,
            "loan_amount": round(loan_amount, 2),
            "mortgage": {
                "annual_rate_pct": round(annual_rate * 100, 2),
                "loan_years": loan_years,
                "monthly_payment": round(monthly_mortgage, 2),
                "total_interest": round(total_interest, 2),
                "amortization_summary": amort_summary,
            },
            "cash_flow": cash_flow,
        }

        # ── Phase 2 (ticks 6-15): Monte Carlo ──
        monte_carlo_results = {}
        n_scenarios = min(ticks * 10, settings.monte_carlo_scenarios)

        if ticks >= 6:
            mc_params = {
                "property_value": property_value,
                "down_payment_pct": down_payment_pct,
                "annual_rate": annual_rate,
                "loan_years": loan_years,
                "monthly_rent": monthly_rent,
                "annual_appreciation": appreciation / 100,
                "vacancy_rate": vacancy_rate,
                "maintenance_pct": maintenance_pct,
                "annual_tax_rate": monthly_taxes * 12 / property_value,
                "annual_insurance": monthly_insurance * 12,
            }
            monte_carlo_results = MonteCarloEngine.run_scenarios(
                mc_params, n_scenarios=n_scenarios, rng=self._rng
            )

        # ── Phase 3 (ticks 16-25): Comparative Analysis ──
        cash_flow_projections = {}
        rent_vs_buy_analysis = {}
        tax_benefit_estimation = {}

        if ticks >= 16:
            # Multi-horizon projections with bear/base/bull scenarios
            scenarios = {}
            for scenario_name, appr_adj, rent_adj in [
                ("bear", -0.02, -0.01),
                ("base", 0, 0),
                ("bull", 0.02, 0.01),
            ]:
                projections = {}
                for horizon in [5, 10, 15, 30]:
                    proj = CashFlowModel.annual_projections(
                        property_value=property_value,
                        rental_income=monthly_rent,
                        appreciation_rate=appreciation / 100 + appr_adj,
                        rental_growth_rate=self._rng.uniform(0.02, 0.04) + rent_adj,
                        years=horizon,
                        mortgage=monthly_mortgage,
                        taxes=monthly_taxes,
                        insurance=monthly_insurance,
                        hoa=monthly_hoa,
                        maintenance_pct=maintenance_pct,
                        vacancy_rate=vacancy_rate,
                    )
                    # Summarize: just keep first, last, and total
                    total_net = sum(p["annual_net_cash_flow"] for p in proj)
                    projections[f"{horizon}_year"] = {
                        "final_property_value": proj[-1]["property_value"],
                        "total_net_cash_flow": round(total_net, 2),
                        "final_year_cash_flow": proj[-1]["annual_net_cash_flow"],
                        "total_equity_gain": proj[-1]["cumulative_equity_gain"],
                    }
                scenarios[scenario_name] = projections

            cash_flow_projections = scenarios

            # Rent vs Buy
            closing_costs = property_value * 0.03
            monthly_own_cost = monthly_mortgage + monthly_taxes + monthly_insurance + monthly_hoa
            comparable_rent = int(monthly_rent * self._rng.uniform(0.90, 1.15))
            be_months = InvestmentMetrics.break_even_months(
                monthly_cost_to_own=monthly_own_cost,
                monthly_rent=comparable_rent,
                upfront_costs=property_value * down_payment_pct + closing_costs,
            )

            rent_vs_buy_analysis = {
                "break_even_months": be_months,
                "monthly_cost_to_own": round(monthly_own_cost, 2),
                "comparable_monthly_rent": comparable_rent,
                "upfront_costs": round(property_value * down_payment_pct + closing_costs, 2),
                "scenarios": {
                    "bear": {
                        "5_year_advantage": "rent" if be_months > 60 else "buy",
                        "10_year_advantage": "buy",
                    },
                    "base": {
                        "5_year_advantage": "buy" if be_months < 60 else "rent",
                        "10_year_advantage": "buy",
                    },
                    "bull": {
                        "5_year_advantage": "buy",
                        "10_year_advantage": "buy",
                    },
                },
            }

            # Tax benefits
            first_year_interest = loan_amount * annual_rate * 0.98  # ~first year mostly interest
            annual_property_tax = monthly_taxes * 12
            tax_benefit = TaxEstimator.annual_tax_benefit(
                mortgage_interest=first_year_interest,
                property_taxes=annual_property_tax,
                marginal_rate=0.24,
            )
            depreciation = TaxEstimator.depreciation_benefit(
                property_value=property_value,
                land_pct=0.20,
                marginal_rate=0.24,
            )
            tax_benefit_estimation = {
                "income_tax": tax_benefit,
                "depreciation": depreciation,
                "total_annual_tax_savings": round(
                    tax_benefit["estimated_annual_savings"]
                    + depreciation["annual_tax_savings"], 2
                ),
            }

        # ── Phase 4 (ticks 26-30): Synthesis ──
        portfolio_metrics_data = {}
        if ticks >= 26 and monte_carlo_results:
            irr_dist = monte_carlo_results.get("irr_distribution", {})
            # Generate synthetic return series for Sharpe calculation
            irr_values = [
                irr_dist.get("p10", 3),
                irr_dist.get("p25", 5),
                irr_dist.get("p50", 7),
                irr_dist.get("p75", 10),
                irr_dist.get("p90", 13),
            ]
            # Expand to more data points for meaningful stats
            returns = []
            for i in range(len(irr_values) - 1):
                for j in range(5):
                    interp = irr_values[i] + (irr_values[i + 1] - irr_values[i]) * j / 5
                    returns.append(interp / 100)

            sharpe = PortfolioMetrics.sharpe_ratio(returns, risk_free_rate=0.04)

            # Simulate property value trajectory for drawdown
            val_trajectory = [property_value]
            v = property_value
            for _ in range(120):  # 10 years monthly
                monthly_change = self._rng.gauss(appreciation / 100 / 12, 0.015)
                v *= (1 + monthly_change)
                val_trajectory.append(v)
            max_dd = PortfolioMetrics.max_drawdown(val_trajectory)

            # Cap rate and cash-on-cash
            annual_noi = cash_flow["net_cash_flow"] * 12
            cash_invested = property_value * down_payment_pct + property_value * 0.03
            cap_rate_val = InvestmentMetrics.cap_rate(annual_noi, property_value)
            coc = InvestmentMetrics.cash_on_cash(annual_noi, cash_invested)

            portfolio_metrics_data = {
                "sharpe_ratio": sharpe,
                "max_drawdown_pct": max_dd,
                "cap_rate_pct": cap_rate_val,
                "cash_on_cash_pct": coc,
                "diversification_score": round(self._rng.uniform(45, 85), 1),
            }

        # ── Comparable Sales Analysis ──
        comparable_sales_analysis = self._generate_comparable_sales(
            seed_document, property_value
        )

        # ── Neighborhood Scoring ──
        neighborhood_scoring = self._generate_neighborhood_scoring()

        # ── Existing sections (market outlook, strategy, risk, etc.) ──
        market_outlook = {
            "summary": "The local market shows moderate growth with steady demand. "
                       "Inventory remains tight, favoring sellers in the short term, "
                       "but interest rate stabilization is creating new buyer opportunities.",
            "trend": self._rng.choice(["bullish", "neutral", "cautiously_optimistic"]),
            "confidence": round(self._rng.uniform(0.65, 0.92), 2),
            "projected_appreciation_pct": appreciation,
            "market_health_score": market_score,
            "key_factors": [
                "Low inventory driving competitive offers",
                "Interest rates stabilizing around 6.0-6.5%",
                "Strong employment growth in metro area",
                "New construction permits up 12% YoY",
            ],
        }

        timing = self._rng.choice(["buy_now", "wait_3_months", "buy_selectively"])
        timing_recommendation = {
            "action": timing,
            "reasoning": self._generate_timing_reasoning(timing),
            "confidence": round(self._rng.uniform(0.60, 0.88), 2),
            "optimal_window_days": self._rng.randint(30, 120),
            "seasonal_factor": self._rng.choice([
                "Spring market typically sees 8-12% more listings",
                "Fall market offers less competition from other buyers",
                "Current season is neutral for timing",
            ]),
        }

        strategy_comparison = [
            {
                "name": "Aggressive",
                "description": "Offer at or above asking price with minimal contingencies",
                "projected_roi_pct": round(self._rng.uniform(8, 18), 1),
                "risk_level": "high",
                "success_probability": round(self._rng.uniform(0.70, 0.90), 2),
                "recommended_offer_pct": round(self._rng.uniform(98, 105), 1),
                "key_trade_offs": [
                    "Higher upfront cost but faster acquisition",
                    "Less room for negotiation on repairs",
                    "Better chance in multi-offer situations",
                ],
            },
            {
                "name": "Balanced",
                "description": "Offer slightly below asking with standard contingencies",
                "projected_roi_pct": round(self._rng.uniform(6, 14), 1),
                "risk_level": "moderate",
                "success_probability": round(self._rng.uniform(0.55, 0.75), 2),
                "recommended_offer_pct": round(self._rng.uniform(93, 98), 1),
                "key_trade_offs": [
                    "Balanced risk and potential return",
                    "Standard inspection and financing contingencies",
                    "Room to negotiate on minor repairs",
                ],
            },
            {
                "name": "Conservative",
                "description": "Offer well below asking with full contingencies",
                "projected_roi_pct": round(self._rng.uniform(3, 10), 1),
                "risk_level": "low",
                "success_probability": round(self._rng.uniform(0.30, 0.55), 2),
                "recommended_offer_pct": round(self._rng.uniform(85, 93), 1),
                "key_trade_offs": [
                    "Maximum protection but lower win rate",
                    "May miss out in competitive markets",
                    "Best for patient investors with long timelines",
                ],
            },
        ]

        risk_assessment = [
            {
                "factor": "Market Correction Risk",
                "severity": self._rng.choice(["low", "moderate", "moderate"]),
                "probability": round(self._rng.uniform(0.10, 0.35), 2),
                "mitigation": "Diversify across property types; maintain 6-month cash reserves",
            },
            {
                "factor": "Interest Rate Volatility",
                "severity": "moderate",
                "probability": round(self._rng.uniform(0.20, 0.50), 2),
                "mitigation": "Lock rates early; consider ARM with rate caps if planning to sell within 5 years",
            },
            {
                "factor": "Vacancy/Rental Risk",
                "severity": self._rng.choice(["low", "moderate"]),
                "probability": round(self._rng.uniform(0.05, 0.25), 2),
                "mitigation": "Target areas with strong rental demand; screen tenants thoroughly",
            },
            {
                "factor": "Maintenance/Capital Expense",
                "severity": "moderate",
                "probability": round(self._rng.uniform(0.30, 0.60), 2),
                "mitigation": "Budget 1-2% of property value annually; get thorough inspections",
            },
        ]

        property_recommendations = self._generate_property_recommendations(
            seed_document, budget_max
        )

        decision_anchors = {
            "max_recommended_price": int(budget_max * self._rng.uniform(0.88, 0.95)),
            "walk_away_price": int(budget_max * 1.05),
            "ideal_cap_rate_pct": round(self._rng.uniform(4.5, 8.0), 1),
            "minimum_cash_on_cash_pct": round(self._rng.uniform(6.0, 12.0), 1),
            "max_dti_ratio_pct": 36,
            "emergency_fund_months": 6,
            "simulation_ticks": ticks,
            "simulation_convergence": round(self._rng.uniform(0.85, 0.98), 2),
        }

        raw_json = {
            "market_outlook": market_outlook,
            "timing_recommendation": timing_recommendation,
            "strategy_comparison": strategy_comparison,
            "risk_assessment": risk_assessment,
            "property_recommendations": property_recommendations,
            "decision_anchors": decision_anchors,
            "financial_analysis": financial_analysis,
            "monte_carlo_results": monte_carlo_results,
            "cash_flow_projections": cash_flow_projections,
            "rent_vs_buy_analysis": rent_vs_buy_analysis,
            "tax_benefit_estimation": tax_benefit_estimation,
            "portfolio_metrics": portfolio_metrics_data,
            "comparable_sales_analysis": comparable_sales_analysis,
            "neighborhood_scoring": neighborhood_scoring,
            "simulation_metadata": {
                "ticks": ticks,
                "seed_hash": hashlib.sha256(seed_document.encode()).hexdigest()[:16],
                "engine": "mirofish_deep_v2",
                "question": question,
                "phases_completed": self._phases_completed(ticks),
            },
        }

        return MiroFishReportData(
            market_outlook=market_outlook,
            timing_recommendation=timing_recommendation,
            strategy_comparison=strategy_comparison,
            risk_assessment=risk_assessment,
            property_recommendations=property_recommendations,
            decision_anchors=decision_anchors,
            financial_analysis=financial_analysis,
            monte_carlo_results=monte_carlo_results,
            cash_flow_projections=cash_flow_projections,
            rent_vs_buy_analysis=rent_vs_buy_analysis,
            tax_benefit_estimation=tax_benefit_estimation,
            portfolio_metrics=portfolio_metrics_data,
            comparable_sales_analysis=comparable_sales_analysis,
            neighborhood_scoring=neighborhood_scoring,
            raw_json=raw_json,
        )

    async def submit_simulation(
        self, seed_document: str, question: str, ticks: int = 30, webhook_url: str | None = None,
    ) -> str:
        job_id = hashlib.sha256(seed_document.encode()).hexdigest()[:12]
        return f"mock-{job_id}"

    async def poll_result(self, job_id: str) -> dict:
        return {"status": "completed", "job_id": job_id}

    async def close(self):
        pass

    @staticmethod
    def _phases_completed(ticks: int) -> list[str]:
        phases = ["base_financials"]
        if ticks >= 6:
            phases.append("monte_carlo")
        if ticks >= 16:
            phases.append("comparative_analysis")
        if ticks >= 26:
            phases.append("synthesis")
        return phases

    def _extract_budget(self, seed: str) -> float:
        """Pull budget_max from the seed document text."""
        for line in seed.split("\n"):
            if "Budget:" in line and "–" in line:
                try:
                    part = line.split("–")[1].strip().replace("$", "").replace(",", "")
                    return float(part)
                except (ValueError, IndexError):
                    pass
        return 500000.0

    def _generate_timing_reasoning(self, timing: str) -> str:
        reasons = {
            "buy_now": (
                "Current market conditions favor immediate action. Inventory is low, "
                "and prices are projected to increase over the next 6 months. Locking in "
                "current rates provides long-term savings."
            ),
            "wait_3_months": (
                "A short wait could yield better opportunities. Seasonal inventory increases "
                "are expected, and potential rate adjustments may improve purchasing power. "
                "Monitor the market closely for price softening."
            ),
            "buy_selectively": (
                "The market is mixed — some segments offer value while others are overheated. "
                "Focus on properties that meet strict criteria: below-median price per sqft, "
                "strong rental demand, and growth-corridor locations."
            ),
        }
        return reasons.get(timing, reasons["buy_selectively"])

    def _generate_property_recommendations(self, seed: str, budget_max: float) -> list:
        """Generate property recommendations based on seed data."""
        property_types = ["Single Family", "Condo", "Duplex", "Townhouse"]
        neighborhoods = [
            "Lincoln Park", "Wicker Park", "Logan Square",
            "Bucktown", "Lakeview", "Uptown", "Andersonville",
        ]
        recs = []
        for i in range(self._rng.randint(3, 5)):
            price = int(budget_max * self._rng.uniform(0.65, 0.95))
            recs.append({
                "rank": i + 1,
                "property_type": self._rng.choice(property_types),
                "neighborhood": self._rng.choice(neighborhoods),
                "estimated_price": price,
                "projected_monthly_cash_flow": int(self._rng.uniform(200, 1200)),
                "cap_rate_pct": round(self._rng.uniform(4.0, 8.5), 1),
                "appreciation_potential": self._rng.choice(["high", "moderate", "above_average"]),
                "fit_score": round(self._rng.uniform(0.70, 0.98), 2),
                "rationale": f"Strong rental demand in {self._rng.choice(neighborhoods)} "
                             f"with projected {round(self._rng.uniform(3, 7), 1)}% annual appreciation. "
                             f"Price point aligns with budget constraints.",
            })
        return sorted(recs, key=lambda r: r["fit_score"], reverse=True)

    def _generate_comparable_sales(self, seed: str, property_value: float) -> dict:
        """Generate comparable sales analysis."""
        sqft = self._rng.randint(1200, 2800)
        price_per_sqft = round(property_value / sqft, 2)
        comps = []
        for i in range(self._rng.randint(4, 7)):
            comp_sqft = self._rng.randint(int(sqft * 0.8), int(sqft * 1.2))
            comp_ppsf = round(price_per_sqft * self._rng.uniform(0.85, 1.15), 2)
            comps.append({
                "address": f"{self._rng.randint(100, 9999)} N {self._rng.choice(['Clark', 'Damen', 'Milwaukee', 'Ashland', 'Western'])} St",
                "sale_price": int(comp_sqft * comp_ppsf),
                "sqft": comp_sqft,
                "price_per_sqft": comp_ppsf,
                "days_on_market": self._rng.randint(5, 90),
                "sale_date_days_ago": self._rng.randint(7, 180),
            })
        median_ppsf = sorted([c["price_per_sqft"] for c in comps])[len(comps) // 2]
        value_indicator = (
            "below_market" if price_per_sqft < median_ppsf * 0.95
            else "above_market" if price_per_sqft > median_ppsf * 1.05
            else "at_market"
        )
        return {
            "subject_price_per_sqft": price_per_sqft,
            "median_price_per_sqft": median_ppsf,
            "value_indicator": value_indicator,
            "comparables_count": len(comps),
            "comparables": comps,
        }

    def _generate_neighborhood_scoring(self) -> dict:
        """Generate neighborhood category scores."""
        categories = {
            "schools": self._rng.randint(55, 95),
            "transit": self._rng.randint(50, 95),
            "dining": self._rng.randint(60, 98),
            "parks_recreation": self._rng.randint(50, 95),
            "safety": self._rng.randint(45, 92),
            "walkability": self._rng.randint(55, 98),
            "grocery": self._rng.randint(60, 95),
        }
        overall = round(sum(categories.values()) / len(categories), 1)
        return {
            "overall_score": overall,
            **categories,
        }


def create_mirofish_client() -> "MiroFishClient | MockMiroFishClient":
    """Factory: returns MockMiroFishClient in mock mode, MiroFishClient in live mode."""
    if settings.mirofish_mode == "mock":
        logger.info("mirofish.using_mock_client")
        return MockMiroFishClient()
    return MiroFishClient()
