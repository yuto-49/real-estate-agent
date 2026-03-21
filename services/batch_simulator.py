"""Batch simulator — orchestrates multiple scenario simulations in parallel."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from services.negotiation_simulator import NegotiationSimulator
from services.scenario_variants import ScenarioVariant, get_variant, SCENARIO_VARIANTS
from config import settings
from services.logging import get_logger

logger = get_logger(__name__)

# Global store for batch runs
_batches: dict[str, dict] = {}


def get_batch(batch_id: str) -> dict | None:
    return _batches.get(batch_id)


class BatchSimulator:
    """Runs multiple NegotiationSimulator instances across scenario variants."""

    def __init__(
        self,
        base_config: dict,
        scenario_names: list[str],
        report_data: dict | None = None,
        persona_data: dict | None = None,
    ):
        self.batch_id = str(uuid.uuid4())
        self.base_config = base_config
        self.report_data = report_data
        self.persona_data = persona_data
        self.created_at = datetime.now(timezone.utc)

        # Resolve scenario variants
        self.scenarios: list[ScenarioVariant] = []
        for name in scenario_names[:settings.max_batch_scenarios]:
            variant = get_variant(name)
            if variant:
                self.scenarios.append(variant)

        if not self.scenarios:
            # Fallback: use balanced_market
            self.scenarios = [v for v in SCENARIO_VARIANTS if v.name == "balanced_market"]

        self.simulators: dict[str, NegotiationSimulator] = {}
        self.results: dict[str, dict] = {}
        self.status = "pending"

        # Register in global store
        _batches[self.batch_id] = self._to_status_dict()

    def _apply_constraints(self, variant: ScenarioVariant) -> dict:
        """Build a per-scenario config by merging base config with variant constraints."""
        config = dict(self.base_config)
        constraints = variant.constraints

        # Adjust initial offer based on discount constraint
        discount_pct = constraints.get("initial_offer_discount_pct")
        if discount_pct is not None:
            config["initial_offer"] = config["asking_price"] * (1 - discount_pct / 100)

        # Apply caller max_rounds as an upper bound while keeping scenario caps.
        requested_max = config.get("max_rounds")
        scenario_max = variant.max_rounds
        if requested_max is not None:
            scenario_max = min(scenario_max, int(requested_max))
        config["max_rounds"] = max(1, min(scenario_max, settings.max_simulation_rounds))

        return config

    async def run_all(self) -> dict:
        """Run all scenarios with limited concurrency."""
        self.status = "running"
        self._update_store()

        semaphore = asyncio.Semaphore(2)

        async def run_one(variant: ScenarioVariant) -> tuple[str, dict]:
            async with semaphore:
                config = self._apply_constraints(variant)
                # Convert persona dicts for the simulator
                persona_dicts = None
                if self.persona_data:
                    persona_dicts = {}
                    for role_key in ("buyer", "seller"):
                        p = self.persona_data.get(role_key)
                        if p:
                            persona_dicts[role_key] = p if isinstance(p, dict) else p
                sim = NegotiationSimulator(
                    config=config,
                    report_data=self.report_data,
                    persona_data=persona_dicts,
                    scenario_constraints=variant.constraints,
                )
                self.simulators[variant.name] = sim
                self._update_store()

                result = await sim.run()
                self.results[variant.name] = result
                self._update_store()
                return variant.name, result

        tasks = [run_one(v) for v in self.scenarios]
        await asyncio.gather(*tasks, return_exceptions=True)

        self.status = "completed"
        result = self._to_result_dict()
        # Merge status info into result so polling still works during transition
        status = self._to_status_dict()
        result["total_scenarios"] = status["total_scenarios"]
        result["completed_scenarios"] = status["completed_scenarios"]
        result["total_progress"] = status["total_progress"]
        result["scenarios"] = status["scenarios"]
        _batches[self.batch_id] = result
        return result

    def _to_status_dict(self) -> dict:
        scenarios_status: list[dict] = []
        for variant in self.scenarios:
            sim = self.simulators.get(variant.name)
            if sim:
                sim_data = sim._to_dict()
                scenarios_status.append({
                    "scenario": variant.name,
                    "status": sim_data["status"],
                    "current_round": sim_data["current_round"],
                    "max_rounds": sim_data["max_rounds"],
                    "progress": sim_data["progress"],
                })
            else:
                scenarios_status.append({
                    "scenario": variant.name,
                    "status": "pending",
                    "current_round": 0,
                    "max_rounds": variant.max_rounds,
                    "progress": 0,
                })

        total_progress = 0
        if scenarios_status:
            total_progress = sum(s["progress"] for s in scenarios_status) // len(scenarios_status)

        return {
            "batch_id": self.batch_id,
            "status": self.status,
            "total_scenarios": len(self.scenarios),
            "completed_scenarios": len(self.results),
            "total_progress": total_progress,
            "scenarios": scenarios_status,
            "created_at": self.created_at.isoformat(),
        }

    def _to_result_dict(self) -> dict:
        outcomes: list[dict] = []
        for variant in self.scenarios:
            result = self.results.get(variant.name)
            if result:
                outcomes.append({
                    "scenario": variant.name,
                    "description": variant.description,
                    "outcome": result.get("outcome", "unknown"),
                    "final_price": result.get("final_price"),
                    "rounds_completed": result.get("current_round", 0),
                    "max_rounds": result.get("max_rounds", variant.max_rounds),
                    "final_spread": result.get("summary", {}).get("final_spread", 0),
                    "price_path": result.get("price_path", []),
                    "transcript": result.get("transcript", []),
                })

        # Compute comparison metrics
        deals = [o for o in outcomes if o["outcome"] == "accepted"]
        win_rate = len(deals) / len(outcomes) * 100 if outcomes else 0
        avg_price = sum(o["final_price"] for o in deals if o["final_price"]) / len(deals) if deals else None
        best = min(deals, key=lambda d: d["final_price"] or float("inf")) if deals else None

        return {
            "batch_id": self.batch_id,
            "status": self.status,
            "outcomes": outcomes,
            "comparison": {
                "win_rate": round(win_rate, 1),
                "deals_reached": len(deals),
                "total_scenarios": len(outcomes),
                "average_deal_price": round(avg_price, 2) if avg_price else None,
                "best_scenario": best["scenario"] if best else None,
                "best_price": best["final_price"] if best else None,
            },
            "created_at": self.created_at.isoformat(),
        }

    def _update_store(self) -> None:
        _batches[self.batch_id] = self._to_status_dict()
