"""Negotiation Simulator — orchestrates automated multi-agent negotiation.

Runs buyer, seller, and broker agents against each other in a simulated
negotiation loop. Each agent uses its real system prompt and Claude API,
but tool calls are intercepted by in-memory mock tools.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import anthropic

from agent.base_agent import BaseAgent
from agent.buyer_agent import BuyerAgent
from agent.seller_agent import SellerAgent
from agent.broker_agent import BrokerAgent
from agent.simulation_tools import SimulationState, create_simulation_tools
from config import settings
from services.logging import get_logger

logger = get_logger(__name__)


# In-memory store for running/completed simulations
_simulations: dict[str, dict] = {}


def get_simulation(sim_id: str) -> dict | None:
    return _simulations.get(sim_id)


def list_simulations() -> list[dict]:
    return list(_simulations.values())


class NegotiationSimulator:
    """Runs an automated negotiation between buyer and seller agents."""

    def __init__(
        self,
        config: dict,
        report_data: dict | None = None,
        persona_data: dict | None = None,
        scenario_constraints: dict | None = None,
    ):
        self.sim_id = str(uuid.uuid4())
        self.config = config
        self.report_data = report_data
        self.persona_data = persona_data
        self.scenario_constraints = scenario_constraints or {}
        self.state = SimulationState(
            negotiation_id=f"sim-{self.sim_id[:8]}",
            property_id=config["property_id"],
            asking_price=config["asking_price"],
            buyer_maximum=config["buyer_maximum"],
            seller_minimum=config["seller_minimum"],
            buyer_latest_price=config["initial_offer"],
            seller_latest_price=config["asking_price"],
        )
        self.transcript: list[dict] = []
        self.max_rounds = min(config.get("max_rounds", 10), settings.max_simulation_rounds)
        self.strategy = config.get("strategy", "balanced")
        self.status = "pending"
        self.outcome = ""
        self.final_price: float | None = None
        self.created_at = datetime.now(timezone.utc)

        # Create agents with fresh Anthropic client
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.buyer = BuyerAgent(self.client)
        self.seller = SellerAgent(self.client)
        self.broker = BrokerAgent(self.client)

        # Create simulation tools
        self.sim_tools = create_simulation_tools(self.state)

        # Register simulation in global store
        _simulations[self.sim_id] = self._to_dict()

    async def run(self) -> dict:
        """Execute the full negotiation simulation loop."""
        self.status = "running"
        self._update_store()

        try:
            # Install simulation tools on agents
            self._install_sim_tools(self.buyer, "buyer")
            self._install_sim_tools(self.seller, "seller")
            self._install_sim_tools(self.broker, "broker")

            # Initial buyer offer
            self._add_transcript("system", f"Simulation started. Property asking price: ${self.config['asking_price']:,.0f}. Buyer initial offer: ${self.config['initial_offer']:,.0f}.")

            for round_num in range(1, self.max_rounds + 1):
                self.state.current_round = round_num
                self._update_store()

                # ── BUYER TURN ──
                buyer_msg = self._build_buyer_message(round_num)
                buyer_context = self._build_agent_context("buyer")
                buyer_result = await self._run_agent_turn(
                    self.buyer, buyer_msg, buyer_context, "buyer"
                )

                if not buyer_result:
                    self.outcome = "failed"
                    break

                self._add_transcript("buyer", buyer_result.get("response", ""), buyer_result.get("tool_calls", []))

                # Check if buyer accepted or walked away
                if self._check_acceptance(buyer_result):
                    self.outcome = "accepted"
                    self.final_price = self.state.buyer_latest_price or self.state.seller_latest_price
                    break
                if self._check_rejection(buyer_result, "buyer"):
                    self.outcome = "rejected"
                    break

                # ── SELLER TURN ──
                seller_msg = self._build_seller_message(round_num)
                seller_context = self._build_agent_context("seller")
                seller_result = await self._run_agent_turn(
                    self.seller, seller_msg, seller_context, "seller"
                )

                if not seller_result:
                    self.outcome = "failed"
                    break

                self._add_transcript("seller", seller_result.get("response", ""), seller_result.get("tool_calls", []))

                # Check if seller accepted
                if self._check_acceptance(seller_result):
                    self.outcome = "accepted"
                    self.final_price = self.state.buyer_latest_price
                    break
                if self._check_rejection(seller_result, "seller"):
                    self.outcome = "rejected"
                    break

                # ── BROKER CHECK ──
                should_broker = self._should_broker_intervene(round_num)
                if should_broker:
                    broker_msg = self._build_broker_message(round_num)
                    broker_context = self._build_agent_context("broker")
                    broker_result = await self._run_agent_turn(
                        self.broker, broker_msg, broker_context, "broker"
                    )
                    if broker_result:
                        self._add_transcript("broker", broker_result.get("response", ""), broker_result.get("tool_calls", []))
                        if self._check_broker_stop(broker_result):
                            self.outcome = "broker_stopped"
                            break

                self._update_store()

            # If we exhausted all rounds
            if not self.outcome:
                self.outcome = "max_rounds"

            self.status = "completed"
            self._update_store()

            return self._to_dict()

        except Exception as e:
            logger.error("simulation.failed", sim_id=self.sim_id, error=str(e))
            self.status = "failed"
            self.outcome = "error"
            self._add_transcript("system", f"Simulation error: {str(e)}")
            self._update_store()
            return self._to_dict()

    def _install_sim_tools(self, agent: BaseAgent, role: str) -> None:
        """Replace agent's tool registry handlers with simulation versions.

        Also registers sim-only tools (like accept_offer) that the agent
        may not have in its registry but needs during simulation.
        """
        for tool_name, handler in self.sim_tools.items():
            if agent.tool_registry.has(tool_name):
                agent.tool_registry.register(tool_name, handler)
            elif tool_name in ("accept_offer", "counter_offer", "place_offer",
                               "evaluate_offer", "mediate_negotiation"):
                # Register sim-critical tools even if agent didn't have them
                agent.tool_registry.register(tool_name, handler)

    async def _run_agent_turn(
        self, agent: BaseAgent, message: str, context: dict, role: str,
    ) -> dict | None:
        """Run one agent turn, handling tool calls with simulation tools."""
        try:
            # Patch _from_role into tool kwargs for counter_offer identification
            original_execute = agent.execute_tool

            async def patched_execute(tool_name: str, tool_input: dict) -> Any:
                tool_input["_from_role"] = role
                if self.report_data:
                    tool_input["_report_data"] = self.report_data
                return await original_execute(tool_name, tool_input)

            agent.execute_tool = patched_execute
            result = await agent.process_message(message, context)
            agent.execute_tool = original_execute

            return result
        except Exception as e:
            logger.error("simulation.agent_turn_failed", role=role, error=str(e))
            self._add_transcript("system", f"{role} agent error: {str(e)}")
            return None

    def _build_buyer_message(self, round_num: int) -> str:
        if round_num == 1:
            return (
                f"You are negotiating to buy property {self.state.property_id}. "
                f"The asking price is ${self.config['asking_price']:,.0f}. "
                f"Your maximum budget is ${self.config['buyer_maximum']:,.0f}. "
                f"Your strategy is '{self.strategy}'. "
                f"Please submit your initial offer using the place_offer or counter_offer tool. "
                f"Start around ${self.config['initial_offer']:,.0f} based on your analysis."
            )
        else:
            return (
                f"Round {round_num} of negotiation for property {self.state.property_id}. "
                f"The seller's latest counter-offer is ${self.state.seller_latest_price:,.0f}. "
                f"Your last offer was ${self.state.buyer_latest_price:,.0f}. "
                f"Your maximum budget is ${self.config['buyer_maximum']:,.0f}. "
                f"The spread is ${abs(self.state.seller_latest_price - self.state.buyer_latest_price):,.0f}. "
                f"Please use the counter_offer tool to submit your response, or accept_offer if you agree."
            )

    def _build_seller_message(self, round_num: int) -> str:
        return (
            f"Round {round_num} of negotiation for property {self.state.property_id}. "
            f"Your asking price is ${self.config['asking_price']:,.0f}. "
            f"Your minimum acceptable price is ${self.config['seller_minimum']:,.0f}. "
            f"The buyer has offered ${self.state.buyer_latest_price:,.0f}. "
            f"Your last counter was ${self.state.seller_latest_price:,.0f}. "
            f"The spread is ${abs(self.state.seller_latest_price - self.state.buyer_latest_price):,.0f}. "
            f"Please use the counter_offer tool to counter, accept_offer to accept, or explain why you reject."
        )

    def _build_broker_message(self, round_num: int) -> str:
        spread = abs(self.state.seller_latest_price - self.state.buyer_latest_price)
        spread_pct = (spread / self.config['asking_price'] * 100) if self.config['asking_price'] > 0 else 0
        return (
            f"You are mediating a negotiation (round {round_num}) for property {self.state.property_id}. "
            f"Buyer position: ${self.state.buyer_latest_price:,.0f}. "
            f"Seller position: ${self.state.seller_latest_price:,.0f}. "
            f"Spread: ${spread:,.0f} ({spread_pct:.1f}%). "
            f"Please use mediate_negotiation to analyze and provide your recommendation. "
            f"If the gap is too large and negotiation is stalling, recommend stopping."
        )

    def _build_agent_context(self, role: str) -> dict:
        """Build context for the agent — only showing what that role should see."""
        context: dict[str, Any] = {
            "simulation_mode": True,
            "negotiation_id": self.state.negotiation_id,
            "property_id": self.state.property_id,
            "current_round": self.state.current_round,
            "max_rounds": self.max_rounds,
            "active_negotiations": [{
                "id": self.state.negotiation_id,
                "property_id": self.state.property_id,
                "status": "counter_pending",
                "round": self.state.current_round,
            }],
        }

        if role == "buyer":
            context["my_latest_offer"] = self.state.buyer_latest_price
            context["their_latest_offer"] = self.state.seller_latest_price
            context["my_maximum"] = self.config["buyer_maximum"]
        elif role == "seller":
            context["my_latest_counter"] = self.state.seller_latest_price
            context["their_latest_offer"] = self.state.buyer_latest_price
            context["my_minimum"] = self.config["seller_minimum"]
            context["asking_price"] = self.config["asking_price"]
        elif role == "broker":
            context["buyer_position"] = self.state.buyer_latest_price
            context["seller_position"] = self.state.seller_latest_price
            context["asking_price"] = self.config["asking_price"]

        # Inject scenario constraints
        if self.scenario_constraints:
            context["scenario_constraints"] = self.scenario_constraints

        # Inject persona data
        if self.persona_data:
            if role == "buyer" and "buyer" in self.persona_data:
                context["persona"] = self.persona_data["buyer"]
            elif role == "seller" and "seller" in self.persona_data:
                context["persona"] = self.persona_data["seller"]
            elif role == "broker":
                context["buyer_persona"] = self.persona_data.get("buyer")
                context["seller_persona"] = self.persona_data.get("seller")

        # Inject intelligence report if available
        if self.report_data:
            if role == "buyer":
                context["intelligence_report"] = {
                    k: v for k, v in self.report_data.items()
                    if k in ("market_outlook", "strategy_comparison", "risk_assessment",
                             "financial_analysis", "monte_carlo_results", "rent_vs_buy_analysis",
                             "decision_anchors")
                }
            elif role == "seller":
                context["intelligence_report"] = {
                    k: v for k, v in self.report_data.items()
                    if k in ("market_outlook", "comparable_sales_analysis",
                             "neighborhood_scoring", "portfolio_metrics")
                }
            elif role == "broker":
                context["intelligence_report"] = self.report_data

        return context

    def _should_broker_intervene(self, round_num: int) -> bool:
        """Broker intervenes when spread >10% after round 3, or prices stall."""
        if round_num < 3:
            return False

        spread = abs(self.state.seller_latest_price - self.state.buyer_latest_price)
        spread_pct = (spread / self.config["asking_price"] * 100) if self.config["asking_price"] > 0 else 0

        if spread_pct > 10:
            return True

        # Check for stall: last two offers from same side are identical
        recent = self.state.offers[-4:] if len(self.state.offers) >= 4 else []
        buyer_prices = [o["price"] for o in recent if o["from"] == "buyer"]
        seller_prices = [o["price"] for o in recent if o["from"] == "seller"]
        if len(buyer_prices) >= 2 and buyer_prices[-1] == buyer_prices[-2]:
            return True
        if len(seller_prices) >= 2 and seller_prices[-1] == seller_prices[-2]:
            return True

        return False

    def _check_acceptance(self, result: dict) -> bool:
        """Check if an agent accepted the offer via tool call."""
        for tc in result.get("tool_calls", []):
            if tc["tool"] == "accept_offer":
                return True
            output = tc.get("output", {})
            if isinstance(output, dict) and output.get("status") == "accepted":
                return True
        return False

    def _check_rejection(self, result: dict, role: str) -> bool:
        """Check if agent explicitly rejected or walked away."""
        response = result.get("response", "").lower()
        rejection_signals = ["walk away", "reject", "cannot accept", "too far apart", "end negotiation"]
        if any(signal in response for signal in rejection_signals):
            # Only treat as rejection if no counter was made
            made_counter = any(
                tc["tool"] in ("counter_offer", "place_offer")
                for tc in result.get("tool_calls", [])
            )
            if not made_counter:
                return True
        return False

    def _check_broker_stop(self, result: dict) -> bool:
        """Check if broker recommended stopping the negotiation."""
        response = result.get("response", "").lower()
        stop_signals = ["recommend stopping", "terminate negotiation", "no viable path",
                        "recommend both parties reassess", "impasse"]
        return any(signal in response for signal in stop_signals)

    def _add_transcript(self, role: str, message: str, tool_calls: list | None = None) -> None:
        entry = {
            "role": role,
            "message": message,
            "round": self.state.current_round,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if tool_calls:
            entry["tool_calls"] = [
                {"tool": tc["tool"], "input": tc.get("input", {}), "output": tc.get("output", {})}
                for tc in tool_calls
            ]
        # Extract price from tool calls
        for tc in (tool_calls or []):
            output = tc.get("output", {})
            if isinstance(output, dict):
                for key in ("offer_price", "counter_price", "final_price"):
                    if key in output:
                        entry["price"] = output[key]
                        break
        self.transcript.append(entry)

    def _update_store(self) -> None:
        _simulations[self.sim_id] = self._to_dict()

    def _to_dict(self) -> dict:
        return {
            "id": self.sim_id,
            "status": self.status,
            "outcome": self.outcome,
            "current_round": self.state.current_round,
            "max_rounds": self.max_rounds,
            "progress": int((self.state.current_round / self.max_rounds) * 100) if self.max_rounds > 0 else 0,
            "final_price": self.final_price,
            "transcript": self.transcript,
            "price_path": self.state.price_path,
            "config": self.config,
            "summary": {
                "rounds_completed": self.state.current_round,
                "buyer_final_position": self.state.buyer_latest_price,
                "seller_final_position": self.state.seller_latest_price,
                "final_spread": round(abs(self.state.seller_latest_price - self.state.buyer_latest_price), 2),
                "outcome": self.outcome,
                "final_price": self.final_price,
            },
            "created_at": self.created_at.isoformat(),
        }
