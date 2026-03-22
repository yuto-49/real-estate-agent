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

        # Build intelligence briefings from report (distilled, role-specific)
        self._buyer_briefing: str = ""
        self._seller_briefing: str = ""
        self._broker_briefing: str = ""
        if self.report_data:
            self._build_intelligence_briefings()

        # Create agents with fresh Anthropic client
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.buyer = BuyerAgent(self.client)
        self.seller = SellerAgent(self.client)
        self.broker = BrokerAgent(self.client)

        # Create simulation tools (includes report-aware negotiation intel tool)
        self.sim_tools = create_simulation_tools(self.state)

        # Register simulation in global store
        _simulations[self.sim_id] = self._to_dict()

    # ── Intelligence Report Integration ──

    @staticmethod
    def derive_config_from_report(report_data: dict, asking_price: float) -> dict:
        """Extract negotiation parameters from a MiroFish intelligence report.

        This implements the MiroFish seed-doc → simulation bridge: the report's
        financial analysis, risk assessment, and decision anchors are distilled
        into concrete negotiation config values.

        Returns a dict of overrides that can be merged into the base sim config.
        """
        overrides: dict[str, Any] = {}

        # ── Decision anchors → price boundaries ──
        anchors = report_data.get("decision_anchors", {})
        if anchors.get("max_recommended_price"):
            overrides["buyer_maximum"] = anchors["max_recommended_price"]
        if anchors.get("walk_away_price"):
            overrides["buyer_walk_away"] = anchors["walk_away_price"]

        # ── Strategy selection from report data ──
        strategies = report_data.get("strategy_comparison", [])
        market = report_data.get("market_outlook", {})
        monte_carlo = report_data.get("monte_carlo_results", {})

        if strategies:
            # Pick strategy based on market conditions + Monte Carlo risk
            market_trend = market.get("trend", "neutral")
            prob_loss = monte_carlo.get("probability_of_loss", 0.5)
            market_score = market.get("market_health_score", 70)

            if prob_loss > 0.3 or market_score < 60:
                # High risk → conservative
                overrides["strategy"] = "conservative"
                target_strat = next((s for s in strategies if s.get("name") == "Conservative"), None)
            elif market_trend in ("bullish", "cautiously_optimistic") and prob_loss < 0.15:
                # Strong market, low risk → aggressive
                overrides["strategy"] = "aggressive"
                target_strat = next((s for s in strategies if s.get("name") == "Aggressive"), None)
            else:
                overrides["strategy"] = "balanced"
                target_strat = next((s for s in strategies if s.get("name") == "Balanced"), None)

            # Extract recommended offer percentage from the chosen strategy
            if target_strat and target_strat.get("recommended_offer_pct"):
                offer_pct = target_strat["recommended_offer_pct"] / 100
                overrides["initial_offer"] = round(asking_price * offer_pct)

        # ── Financial analysis → seller minimum estimate ──
        financial = report_data.get("financial_analysis", {})
        comps = report_data.get("comparable_sales_analysis", {})

        if comps.get("median_price_per_sqft") and comps.get("value_indicator"):
            indicator = comps["value_indicator"]
            if indicator == "above_market":
                # Property is overpriced — lower initial offer
                if "initial_offer" not in overrides:
                    overrides["initial_offer"] = round(asking_price * 0.90)
            elif indicator == "below_market":
                # Property is a deal — don't lowball too much
                if "initial_offer" not in overrides:
                    overrides["initial_offer"] = round(asking_price * 0.97)

        # ── Timing → urgency constraints ──
        timing = report_data.get("timing_recommendation", {})
        if timing.get("action") == "buy_now":
            overrides.setdefault("scenario_constraints", {})["buyer_urgency"] = "high"
        elif timing.get("action") == "wait_3_months":
            overrides.setdefault("scenario_constraints", {})["buyer_urgency"] = "low"

        # ── Risk assessment → max rounds (higher risk = fewer rounds, cut losses) ──
        risks = report_data.get("risk_assessment", [])
        high_risks = [r for r in risks if r.get("severity") in ("high",) and r.get("probability", 0) > 0.3]
        if high_risks:
            overrides["max_rounds"] = min(overrides.get("max_rounds", 10), 8)

        return overrides

    def _build_intelligence_briefings(self) -> None:
        """Distill report_data into concise, role-specific negotiation briefings.

        Instead of dumping raw financial JSON into agent context, we produce
        natural-language summaries with specific numbers agents can cite.
        This mirrors MiroFish's approach of shaping agent behavior from seed data.
        """
        rd = self.report_data
        if not rd:
            return

        asking = self.config.get("asking_price", 0)
        initial = self.config.get("initial_offer", 0)

        # ── Extract key metrics ──
        market = rd.get("market_outlook", {})
        anchors = rd.get("decision_anchors", {})
        strategies = rd.get("strategy_comparison", [])
        risks = rd.get("risk_assessment", [])
        financial = rd.get("financial_analysis", {})
        monte_carlo = rd.get("monte_carlo_results", {})
        comps = rd.get("comparable_sales_analysis", {})
        neighborhood = rd.get("neighborhood_scoring", {})
        timing = rd.get("timing_recommendation", {})
        rent_buy = rd.get("rent_vs_buy_analysis", {})
        cash_flow = financial.get("cash_flow", {})

        # ── BUYER BRIEFING ──
        buyer_lines = ["## Intelligence Briefing (from MiroFish Analysis)"]

        # Market position
        trend = market.get("trend", "neutral")
        confidence = market.get("confidence", 0)
        buyer_lines.append(f"**Market trend**: {trend} (confidence: {confidence:.0%})")
        if market.get("projected_appreciation_pct"):
            buyer_lines.append(f"**Projected appreciation**: {market['projected_appreciation_pct']}%/year")

        # Comparable sales
        if comps.get("value_indicator"):
            ind = comps["value_indicator"]
            median_ppsf = comps.get("median_price_per_sqft", 0)
            subject_ppsf = comps.get("subject_price_per_sqft", 0)
            buyer_lines.append(
                f"**Comparable sales**: Asking price is **{ind.replace('_', ' ')}** "
                f"(${subject_ppsf:.0f}/sqft vs median ${median_ppsf:.0f}/sqft)"
            )

        # Decision anchors
        if anchors.get("max_recommended_price"):
            buyer_lines.append(f"**Maximum recommended price**: ${anchors['max_recommended_price']:,.0f}")
        if anchors.get("walk_away_price"):
            buyer_lines.append(f"**Walk-away price**: ${anchors['walk_away_price']:,.0f}")

        # Strategy recommendation
        chosen_strat = next((s for s in strategies if s.get("name", "").lower() == self.strategy), None)
        if chosen_strat:
            buyer_lines.append(
                f"**Recommended strategy**: {chosen_strat['name']} — "
                f"offer at ~{chosen_strat.get('recommended_offer_pct', 95)}% of asking, "
                f"success probability: {chosen_strat.get('success_probability', 0):.0%}"
            )

        # Monte Carlo risk
        if monte_carlo.get("probability_of_loss") is not None:
            buyer_lines.append(
                f"**Investment risk**: {monte_carlo['probability_of_loss']:.1%} probability of loss "
                f"over {monte_carlo.get('hold_years', 10)} years"
            )
            irr = monte_carlo.get("irr_distribution", {})
            if irr.get("p50"):
                buyer_lines.append(f"**Expected IRR**: {irr['p50']}% (median), range {irr.get('p10', '?')}% - {irr.get('p90', '?')}%")

        # Cash flow
        if cash_flow.get("net_cash_flow"):
            buyer_lines.append(f"**Monthly cash flow**: ${cash_flow['net_cash_flow']:,.0f}/mo after expenses")

        # Timing
        if timing.get("action"):
            buyer_lines.append(f"**Timing**: {timing['action'].replace('_', ' ')} — {timing.get('reasoning', '')[:120]}")

        # Negotiation directives
        buyer_lines.append("\n**Negotiation directives from analysis:**")
        buyer_lines.append(f"- Start your offer around ${initial:,.0f} ({initial/asking*100:.1f}% of asking)")
        if anchors.get("max_recommended_price"):
            buyer_lines.append(f"- Do NOT exceed ${anchors['max_recommended_price']:,.0f} under any circumstances")
        if comps.get("value_indicator") == "above_market":
            buyer_lines.append("- The property is ABOVE market value — use comps data to justify a lower price")
        elif comps.get("value_indicator") == "below_market":
            buyer_lines.append("- The property is BELOW market value — don't lowball excessively or you'll lose it")

        high_risks = [r for r in risks if r.get("probability", 0) > 0.3]
        if high_risks:
            buyer_lines.append(f"- Key risks to cite: {', '.join(r.get('factor', '') for r in high_risks[:3])}")

        self._buyer_briefing = "\n".join(buyer_lines)

        # ── SELLER BRIEFING ──
        seller_lines = ["## Intelligence Briefing (Market Context)"]
        seller_lines.append(f"**Market trend**: {trend} (confidence: {confidence:.0%})")
        if market.get("projected_appreciation_pct"):
            seller_lines.append(f"**Projected appreciation**: {market['projected_appreciation_pct']}%/year")

        if comps.get("value_indicator"):
            seller_lines.append(
                f"**Comparable sales**: Property is **{comps['value_indicator'].replace('_', ' ')}** "
                f"(${comps.get('subject_price_per_sqft', 0):.0f}/sqft vs median ${comps.get('median_price_per_sqft', 0):.0f}/sqft)"
            )

        if neighborhood.get("overall_score"):
            seller_lines.append(f"**Neighborhood score**: {neighborhood['overall_score']}/100")
            top_features = sorted(
                [(k, v) for k, v in neighborhood.items() if k != "overall_score" and isinstance(v, (int, float))],
                key=lambda x: x[1], reverse=True,
            )[:3]
            if top_features:
                seller_lines.append(f"**Strongest features**: {', '.join(f'{k} ({v}/100)' for k, v in top_features)}")

        seller_lines.append("\n**Negotiation directives:**")
        if comps.get("value_indicator") == "below_market":
            seller_lines.append("- Your property is BELOW market — hold firm on price, emphasize value")
        elif comps.get("value_indicator") == "above_market":
            seller_lines.append("- Your property is ABOVE market — be prepared to make concessions")
        if trend in ("bullish", "cautiously_optimistic"):
            seller_lines.append("- Market is trending up — you have leverage, don't rush to concede")
        low_risks = [r for r in risks if r.get("severity") == "low"]
        if low_risks:
            seller_lines.append(f"- Low-risk factors working in your favor: {', '.join(r.get('factor', '') for r in low_risks[:2])}")

        self._seller_briefing = "\n".join(seller_lines)

        # ── BROKER BRIEFING ──
        broker_lines = ["## Intelligence Briefing (Full Market Analysis)"]
        broker_lines.append(f"**Market**: {trend}, health score {market.get('market_health_score', 'N/A')}/100")
        if comps:
            broker_lines.append(
                f"**Comps**: {comps.get('value_indicator', 'N/A').replace('_', ' ')}, "
                f"median ${comps.get('median_price_per_sqft', 0):.0f}/sqft"
            )
        if monte_carlo.get("mean_irr"):
            broker_lines.append(f"**Expected IRR**: {monte_carlo['mean_irr']}%")
        if monte_carlo.get("probability_of_loss") is not None:
            broker_lines.append(f"**Loss probability**: {monte_carlo['probability_of_loss']:.1%}")
        if anchors.get("max_recommended_price"):
            broker_lines.append(f"**Buyer's data-backed max**: ${anchors['max_recommended_price']:,.0f}")
        broker_lines.append(f"**Asking**: ${asking:,.0f}, **Buyer initial**: ${initial:,.0f}")

        # ZOPA estimate from report
        if anchors.get("max_recommended_price") and self.config.get("seller_minimum"):
            zopa_low = self.config["seller_minimum"]
            zopa_high = anchors["max_recommended_price"]
            if zopa_high >= zopa_low:
                midpoint = (zopa_low + zopa_high) / 2
                broker_lines.append(
                    f"**Estimated ZOPA**: ${zopa_low:,.0f} – ${zopa_high:,.0f} (midpoint: ${midpoint:,.0f})"
                )
            else:
                broker_lines.append("**ZOPA**: None detected — buyer's max is below seller's minimum")

        self._broker_briefing = "\n".join(broker_lines)

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
                    # Don't fail the whole simulation — skip this round
                    self._add_transcript("system", f"Buyer agent unavailable in round {round_num}, skipping.")
                    consecutive_failures = getattr(self, '_consecutive_failures', 0) + 1
                    self._consecutive_failures = consecutive_failures
                    if consecutive_failures >= 3:
                        self.outcome = "failed"
                        break
                    continue

                self._consecutive_failures = 0
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
                    self._add_transcript("system", f"Seller agent unavailable in round {round_num}, skipping.")
                    consecutive_failures = getattr(self, '_consecutive_failures', 0) + 1
                    self._consecutive_failures = consecutive_failures
                    if consecutive_failures >= 3:
                        self.outcome = "failed"
                        break
                    continue

                self._consecutive_failures = 0
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

        except anthropic.AuthenticationError as e:
            logger.error("simulation.auth_failed", sim_id=self.sim_id, error=str(e))
            self.status = "failed"
            self.outcome = "error"
            self._add_transcript("system", "Authentication failed — check ANTHROPIC_API_KEY in .env")
            self._update_store()
            return self._to_dict()
        except anthropic.NotFoundError as e:
            logger.error("simulation.model_not_found", sim_id=self.sim_id, error=str(e))
            self.status = "failed"
            self.outcome = "error"
            self._add_transcript("system", f"Model not found: {str(e)}. Check the model ID in base_agent.py")
            self._update_store()
            return self._to_dict()
        except Exception as e:
            logger.error("simulation.failed", sim_id=self.sim_id, error=str(e), exc_info=True)
            self.status = "failed"
            self.outcome = "error"
            self._add_transcript("system", f"Simulation error: {type(e).__name__}: {str(e)}")
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
                               "evaluate_offer", "mediate_negotiation",
                               "get_negotiation_intel"):
                # Register sim-critical tools even if agent didn't have them
                agent.tool_registry.register(tool_name, handler)

    async def _run_agent_turn(
        self, agent: BaseAgent, message: str, context: dict, role: str,
        max_retries: int = 2,
    ) -> dict | None:
        """Run one agent turn, handling tool calls with simulation tools.

        Retries on transient API errors (rate limits, overloaded, network).
        """
        original_execute = agent.execute_tool

        async def patched_execute(tool_name: str, tool_input: dict) -> Any:
            tool_input["_from_role"] = role
            if self.report_data:
                tool_input["_report_data"] = self.report_data
            return await original_execute(tool_name, tool_input)

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                agent.execute_tool = patched_execute
                result = await agent.process_message(message, context)
                agent.execute_tool = original_execute
                return result
            except anthropic.RateLimitError as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning("simulation.rate_limited", role=role, attempt=attempt, wait=wait)
                await asyncio.sleep(wait)
            except anthropic.APIStatusError as e:
                last_error = e
                if e.status_code in (429, 500, 502, 503, 529):
                    wait = 2 ** attempt
                    logger.warning("simulation.api_transient_error", role=role, status=e.status_code, attempt=attempt)
                    await asyncio.sleep(wait)
                else:
                    # Non-retryable API error (e.g. 400, 401, 404)
                    logger.error("simulation.agent_turn_failed", role=role, error=str(e))
                    self._add_transcript("system", f"{role} agent error: {str(e)}")
                    agent.execute_tool = original_execute
                    return None
            except anthropic.APIConnectionError as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning("simulation.connection_error", role=role, attempt=attempt)
                await asyncio.sleep(wait)
            except Exception as e:
                logger.error("simulation.agent_turn_failed", role=role, error=str(e))
                self._add_transcript("system", f"{role} agent error: {str(e)}")
                agent.execute_tool = original_execute
                return None

        # All retries exhausted
        logger.error("simulation.agent_turn_exhausted", role=role, error=str(last_error))
        self._add_transcript("system", f"{role} agent failed after {max_retries + 1} attempts: {str(last_error)}")
        agent.execute_tool = original_execute
        return None

    def _build_buyer_message(self, round_num: int) -> str:
        report_hint = ""
        if self._buyer_briefing and round_num == 1:
            report_hint = (
                " You have a MiroFish intelligence report — use the data in your "
                "intelligence_briefing to justify your offer price and strategy. "
                "Cite specific numbers (comps, IRR, risk %) when explaining your position."
            )

        if round_num == 1:
            return (
                f"You are negotiating to buy property {self.state.property_id}. "
                f"The asking price is ${self.config['asking_price']:,.0f}. "
                f"Your maximum budget is ${self.config['buyer_maximum']:,.0f}. "
                f"Your strategy is '{self.strategy}'. "
                f"Please submit your initial offer using the place_offer or counter_offer tool. "
                f"Start around ${self.config['initial_offer']:,.0f} based on your analysis."
                f"{report_hint}"
            )
        else:
            spread = abs(self.state.seller_latest_price - self.state.buyer_latest_price)
            spread_pct = (spread / self.config['asking_price'] * 100) if self.config['asking_price'] > 0 else 0
            accept_hint = ""
            if spread_pct < 3 and self._buyer_briefing:
                accept_hint = " The spread is very small — consider accepting if the price is within your intelligence report's recommended range."
            return (
                f"Round {round_num} of negotiation for property {self.state.property_id}. "
                f"The seller's latest counter-offer is ${self.state.seller_latest_price:,.0f}. "
                f"Your last offer was ${self.state.buyer_latest_price:,.0f}. "
                f"Your maximum budget is ${self.config['buyer_maximum']:,.0f}. "
                f"The spread is ${spread:,.0f} ({spread_pct:.1f}%). "
                f"Please use the counter_offer tool to submit your response, or accept_offer if you agree."
                f"{accept_hint}"
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

        # Inject intelligence briefing (distilled, not raw data)
        if self.report_data:
            if role == "buyer" and self._buyer_briefing:
                context["intelligence_briefing"] = self._buyer_briefing
                # Also include key anchors as structured data for tool use
                anchors = self.report_data.get("decision_anchors", {})
                if anchors:
                    context["price_anchors"] = {
                        "max_recommended": anchors.get("max_recommended_price"),
                        "walk_away": anchors.get("walk_away_price"),
                        "ideal_cap_rate": anchors.get("ideal_cap_rate_pct"),
                    }
            elif role == "seller" and self._seller_briefing:
                context["intelligence_briefing"] = self._seller_briefing
            elif role == "broker" and self._broker_briefing:
                context["intelligence_briefing"] = self._broker_briefing

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
