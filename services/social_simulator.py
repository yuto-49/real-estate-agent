"""Social Behavior Simulation Engine.

Runs opinion dynamics across a synthetic household social graph.
Each round, active households consider neighbor opinions and update
their stance via Claude API reasoning + weighted drift formula.

Outputs narrative clusters and sentiment deltas that feed into
the MiroFish report bridge for negotiation intelligence.
"""

import asyncio
import json
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, cast

import anthropic
from sqlalchemy import select, update

from config import settings
from db.database import async_session
from db.models import (
    HouseholdProfile,
    HouseholdSocialEdge,
    SocialSimulationAction,
    SocialSimulationRun,
)
from services.logging import get_logger

logger = get_logger(__name__)

TOPICS = [
    "market_prices",
    "eviction_policy",
    "voucher_program",
    "neighborhood_safety",
]

TOPIC_DESCRIPTIONS = {
    "market_prices": (
        "local housing prices, affordability, and market trends"
    ),
    "eviction_policy": (
        "tenant protections, eviction moratoriums, "
        "and landlord-tenant relations"
    ),
    "voucher_program": (
        "Section 8 / housing choice vouchers "
        "and subsidized housing programs"
    ),
    "neighborhood_safety": (
        "crime, community investment, policing, "
        "and neighborhood quality"
    ),
}

# In-memory store for running simulations
_social_sims: dict[str, dict[str, Any]] = {}


def get_social_sim(run_id: str) -> dict[str, Any] | None:
    return _social_sims.get(run_id)


class SocialSimulator:
    """Runs opinion dynamics simulation across household social graph."""

    def __init__(
        self,
        run_id: str,
        trigger_user_id: str,
        households: list[HouseholdProfile],
        edges: list[HouseholdSocialEdge],
        topics: list[str] | None = None,
        max_rounds: int = 10,
        active_fraction: float = 0.3,
    ):
        self.run_id = run_id
        self.trigger_user_id = trigger_user_id
        self.households: dict[str, HouseholdProfile] = {
            cast(str, h.id): h for h in households
        }
        self.edges = edges
        self.topics = topics or TOPICS
        self.max_rounds = max_rounds
        self.active_fraction = active_fraction

        # Build adjacency: household_id → [(neighbor_id, weight, type)]
        self.neighbors: defaultdict[str, list[tuple[str, float, str]]] = (
            defaultdict(list)
        )
        for edge in edges:
            src = cast(str, edge.source_id)
            tgt = cast(str, edge.target_id)
            wt = cast(float, edge.edge_weight)
            etype = cast(str, edge.edge_type)
            self.neighbors[src].append((tgt, wt, etype))
            self.neighbors[tgt].append((src, wt, etype))

        # Track opinion state per household per topic
        self.opinions: dict[str, dict[str, float]] = {}
        for h in households:
            hid = cast(str, h.id)
            sentiment = cast(float, h.housing_market_sentiment)
            policy = cast(float, h.policy_support_score)
            satisfaction = cast(float, h.neighborhood_satisfaction)
            self.opinions[hid] = {
                "market_prices": sentiment,
                "eviction_policy": policy,
                "voucher_program": policy * 0.8,
                "neighborhood_safety": satisfaction * 2 - 1,
            }

        # Track round-by-round deltas for convergence detection
        self.round_deltas: list[float] = []
        self._previous_opinions: dict[str, dict[str, float]] = {}

        # Claude client
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
        )
        self.semaphore = asyncio.Semaphore(5)

    async def run(self) -> dict[str, Any]:
        """Execute the full social simulation loop."""
        logger.info(
            "social_sim.start",
            run_id=self.run_id,
            households=len(self.households),
            rounds=self.max_rounds,
        )

        # Track initial opinions for delta calculation
        initial_opinions = {
            hid: dict(ops) for hid, ops in self.opinions.items()
        }

        actions_all: list[dict[str, Any]] = []

        for round_num in range(1, self.max_rounds + 1):
            # Update DB status
            async with async_session() as db:
                await db.execute(
                    update(SocialSimulationRun)
                    .where(SocialSimulationRun.id == self.run_id)
                    .values(current_round=round_num, status="running")
                )
                await db.commit()

            _social_sims[self.run_id] = {
                "id": self.run_id,
                "status": "running",
                "current_round": round_num,
                "total_rounds": self.max_rounds,
            }

            # Select active households
            active_ids = self._select_active_households()
            logger.info(
                "social_sim.round",
                run_id=self.run_id,
                round_num=round_num,
                active=len(active_ids),
            )

            # Process each active household concurrently
            tasks = [
                self._process_household_topic(hid, topic, round_num)
                for hid in active_ids
                for topic in self.topics
            ]

            results = await asyncio.gather(
                *tasks, return_exceptions=True,
            )

            round_actions: list[dict[str, Any]] = []
            for gather_result in results:
                if isinstance(gather_result, BaseException):
                    logger.error(
                        "social_sim.household_error",
                        error=str(gather_result),
                    )
                    continue
                if gather_result:
                    round_actions.append(gather_result)

            # Write actions to DB
            async with async_session() as db:
                for action_data in round_actions:
                    action = SocialSimulationAction(
                        run_id=self.run_id,
                        round_num=action_data["round_num"],
                        household_id=action_data["household_id"],
                        action_type=action_data["action_type"],
                        topic=action_data["topic"],
                        content=action_data["content"],
                        sentiment_value=action_data["sentiment_value"],
                        influenced_by=action_data["influenced_by"],
                    )
                    db.add(action)
                await db.commit()

            actions_all.extend(round_actions)

            # Check convergence
            avg_delta = self._compute_round_delta()
            self.round_deltas.append(avg_delta)
            logger.info(
                "social_sim.round_delta",
                run_id=self.run_id,
                round_num=round_num,
                avg_delta=avg_delta,
            )

            if avg_delta < 0.02 and round_num >= 3:
                logger.info(
                    "social_sim.converged",
                    run_id=self.run_id,
                    round_num=round_num,
                )
                break

        # Build final outputs
        narrative_output = self._detect_narratives()
        sentiment_delta = self._compute_sentiment_delta(initial_opinions)

        # Update DB with final results
        async with async_session() as db:
            await db.execute(
                update(SocialSimulationRun)
                .where(SocialSimulationRun.id == self.run_id)
                .values(
                    status="completed",
                    current_round=len(self.round_deltas),
                    narrative_output=narrative_output,
                    sentiment_delta=sentiment_delta,
                    completed_at=datetime.now(UTC),
                )
            )
            await db.commit()

        result: dict[str, Any] = {
            "id": self.run_id,
            "status": "completed",
            "total_rounds": len(self.round_deltas),
            "narrative_output": narrative_output,
            "sentiment_delta": sentiment_delta,
            "action_count": len(actions_all),
        }
        _social_sims[self.run_id] = result
        return result

    def _select_active_households(self) -> list[str]:
        """Select households to be active this round."""
        import random

        all_ids = list(self.households.keys())
        n_active = max(1, int(len(all_ids) * self.active_fraction))

        # Weight by influence_weight, vocal households more likely
        weights: list[float] = []
        for hid in all_ids:
            h = self.households[hid]
            w = cast(float, h.influence_weight)
            style = h.communication_style
            if style and style.value == "vocal":
                w *= 1.5
            elif style and style.value == "passive":
                w *= 0.5
            weights.append(w)

        # Normalize
        total = sum(weights)
        if total == 0:
            return random.sample(all_ids, min(n_active, len(all_ids)))

        weights = [w / total for w in weights]
        selected: set[str] = set()
        attempts = 0
        while len(selected) < n_active and attempts < n_active * 3:
            pick = random.choices(all_ids, weights=weights, k=1)[0]
            selected.add(pick)
            attempts += 1

        return list(selected)

    async def _process_household_topic(
        self, household_id: str, topic: str, round_num: int,
    ) -> dict[str, Any] | None:
        """Process one household's opinion update for one topic."""
        async with self.semaphore:
            h = self.households[household_id]
            current_opinion = self.opinions[household_id][topic]

            # Gather neighbor opinions for this topic
            neighbor_opinions = self._gather_neighbor_opinions(
                household_id, topic,
            )

            if not neighbor_opinions:
                return {
                    "round_num": round_num,
                    "household_id": household_id,
                    "action_type": "go_silent",
                    "topic": topic,
                    "content": "No social input this round.",
                    "sentiment_value": current_opinion,
                    "influenced_by": [],
                }

            # Call Claude for opinion reasoning
            llm_delta, content, action_type = await self._get_llm_opinion(
                h, topic, current_opinion, neighbor_opinions, round_num,
            )

            # Apply opinion drift formula
            new_opinion = self._apply_opinion_drift(
                h, current_opinion, neighbor_opinions, llm_delta,
            )

            # Store previous for delta tracking
            self._previous_opinions.setdefault(
                household_id, {},
            )[topic] = current_opinion

            # Update opinion state
            self.opinions[household_id][topic] = new_opinion

            return {
                "round_num": round_num,
                "household_id": household_id,
                "action_type": action_type,
                "topic": topic,
                "content": content,
                "sentiment_value": round(new_opinion, 4),
                "influenced_by": [
                    n["id"] for n in neighbor_opinions[:5]
                ],
            }

    def _gather_neighbor_opinions(
        self, household_id: str, topic: str,
    ) -> list[dict[str, Any]]:
        """Gather weighted neighbor opinions for a specific topic."""
        result: list[dict[str, Any]] = []
        for neighbor_id, weight, edge_type in self.neighbors.get(
            household_id, [],
        ):
            if neighbor_id not in self.opinions:
                continue
            neighbor_opinion = self.opinions[neighbor_id].get(topic, 0.0)
            neighbor_h = self.households.get(neighbor_id)
            if not neighbor_h:
                continue
            style = neighbor_h.communication_style
            result.append({
                "id": neighbor_id,
                "opinion": neighbor_opinion,
                "weight": weight,
                "edge_type": edge_type,
                "income_band": cast(str, neighbor_h.income_band),
                "communication_style": (
                    style.value if style else "passive"
                ),
            })
        return result

    async def _get_llm_opinion(
        self,
        household: HouseholdProfile,
        topic: str,
        current_opinion: float,
        neighbor_opinions: list[dict[str, Any]],
        round_num: int,
    ) -> tuple[float, str, str]:
        """Call Claude to reason about opinion update.

        Returns (delta, content, action_type).
        """
        topic_desc = TOPIC_DESCRIPTIONS.get(topic, topic)

        # Summarize neighbor stances
        neighbor_summary = []
        for n in neighbor_opinions[:8]:
            op = n["opinion"]
            if op > 0.2:
                stance = "supportive"
            elif op < -0.2:
                stance = "opposed"
            else:
                stance = "neutral"
            neighbor_summary.append(
                f"- A {n['edge_type']} "
                f"({n['income_band']} income, "
                f"{n['communication_style']}) "
                f"is {stance} ({op:+.2f})"
            )

        if current_opinion > 0.2:
            stance_word = "supportive"
        elif current_opinion < -0.2:
            stance_word = "opposed"
        else:
            stance_word = "neutral"

        monthly_income = cast(float, household.monthly_income)
        housing_cost = cast(float, household.monthly_housing_cost)
        cost_burden = (
            round(housing_cost / monthly_income * 100, 1)
            if monthly_income > 0
            else 0
        )

        style = household.communication_style
        style_val = style.value if style else "passive"
        eviction_risk = cast(float, household.eviction_risk)
        neighbors_text = (
            chr(10).join(neighbor_summary)
            if neighbor_summary
            else "No neighbor input this round."
        )

        prompt = (
            "You are simulating the opinion of a household "
            "in a workforce housing community.\n\n"
            "HOUSEHOLD PROFILE:\n"
            f"- Income: {household.income_band} "
            f"(${monthly_income:,.0f}/month)\n"
            f"- Housing: {household.housing_type}, "
            f"cost burden: {cost_burden}% of income\n"
            f"- Household size: {household.household_size}, "
            f"children: {household.num_children}\n"
            f"- Language: {household.primary_language}\n"
            f"- Age bracket: {household.age_bracket}\n"
            f"- Eviction risk: {eviction_risk:.1%}\n"
            f"- Communication style: {style_val}\n"
            f"- Current stance on {topic} ({topic_desc}): "
            f"{stance_word} ({current_opinion:+.3f})\n\n"
            f"NEIGHBOR OPINIONS (round {round_num}):\n"
            f"{neighbors_text}\n\n"
            "Based on this household's circumstances and their "
            "neighbors' stances, generate:\n"
            "1. A brief opinion statement (1-2 sentences) this "
            f"household might express about {topic_desc}\n"
            '2. An action type: "post_opinion" (share view), '
            '"share_narrative" (tell a story), '
            '"update_stance" (quietly shift), '
            'or "go_silent" (disengage)\n'
            "3. An opinion shift value between -0.5 and +0.5 "
            "(how much their opinion should move, "
            "considering their personality and social pressure)\n\n"
            "Respond in this exact JSON format:\n"
            '{"statement": "...", '
            '"action": "post_opinion|share_narrative'
            '|update_stance|go_silent", '
            '"delta": 0.0}'
        )

        try:
            response = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )

            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text = block.text.strip()
                    break

            # Parse JSON from response (handle markdown code blocks)
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)
            delta = max(-0.5, min(0.5, float(data.get("delta", 0.0))))
            content = data.get("statement", "")
            action_type = data.get("action", "update_stance")

            valid_actions = {
                "post_opinion",
                "share_narrative",
                "update_stance",
                "go_silent",
            }
            if action_type not in valid_actions:
                action_type = "update_stance"

            return delta, content, action_type

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(
                "social_sim.llm_parse_error",
                household_id=household.id,
                error=str(e),
            )
            return 0.0, "No clear opinion this round.", "go_silent"
        except anthropic.APIError as e:
            logger.warning(
                "social_sim.llm_api_error",
                household_id=household.id,
                error=str(e),
            )
            return 0.0, "Unable to form opinion.", "go_silent"

    def _apply_opinion_drift(
        self,
        household: HouseholdProfile,
        current: float,
        neighbor_opinions: list[dict[str, Any]],
        llm_delta: float,
    ) -> float:
        """Apply the opinion drift formula.

        new = (stability * current)
            + ((1 - stability) * weighted_neighbor_avg)
            + (0.1 * llm_delta)
        """
        stability = cast(float, household.opinion_stability)

        # Weighted neighbor average
        if neighbor_opinions:
            total_weight = sum(
                n["weight"] for n in neighbor_opinions
            )
            if total_weight > 0:
                peer_avg = (
                    sum(
                        n["opinion"] * n["weight"]
                        for n in neighbor_opinions
                    )
                    / total_weight
                )
            else:
                peer_avg = current
        else:
            peer_avg = current

        new_opinion = (
            stability * current
            + (1 - stability) * peer_avg
            + 0.1 * llm_delta
        )

        # Clamp to [-1, 1]
        return round(max(-1.0, min(1.0, new_opinion)), 4)

    def _compute_round_delta(self) -> float:
        """Compute average opinion change across all households."""
        if not self._previous_opinions:
            return 1.0  # first round, max delta

        total_delta = 0.0
        count = 0
        for hid, prev_topics in self._previous_opinions.items():
            for topic, prev_val in prev_topics.items():
                current_val = self.opinions.get(
                    hid, {},
                ).get(topic, prev_val)
                total_delta += abs(current_val - prev_val)
                count += 1

        return total_delta / count if count > 0 else 0.0

    def _compute_sentiment_delta(
        self, initial_opinions: dict[str, dict[str, float]],
    ) -> dict[str, dict[str, float]]:
        """Compute how opinions shifted from initial to final state."""
        delta: dict[str, dict[str, float]] = {}
        for topic in self.topics:
            initial_values = [
                initial_opinions[hid].get(topic, 0.0)
                for hid in self.households
            ]
            final_values = [
                self.opinions[hid].get(topic, 0.0)
                for hid in self.households
            ]

            n = len(initial_values) if initial_values else 1
            initial_avg = sum(initial_values) / n
            final_avg = sum(final_values) / n

            volatility = (
                sum(
                    abs(f - i)
                    for f, i in zip(final_values, initial_values)
                )
                / n
            )

            delta[topic] = {
                "initial_avg": round(initial_avg, 4),
                "final_avg": round(final_avg, 4),
                "shift": round(final_avg - initial_avg, 4),
                "volatility": round(volatility, 4),
            }
        return delta

    def _detect_narratives(self) -> dict[str, dict[str, Any]]:
        """Cluster households by opinion similarity per topic."""
        narratives: dict[str, dict[str, Any]] = {}

        for topic in self.topics:
            supportive: list[dict[str, Any]] = []
            opposed: list[dict[str, Any]] = []
            neutral: list[dict[str, Any]] = []

            for hid, ops in self.opinions.items():
                val = ops.get(topic, 0.0)
                h = self.households[hid]
                entry: dict[str, Any] = {
                    "id": hid,
                    "opinion": val,
                    "income_band": cast(str, h.income_band),
                    "housing_type": cast(str, h.housing_type),
                    "influence": cast(float, h.influence_weight),
                }
                if val > 0.2:
                    supportive.append(entry)
                elif val < -0.2:
                    opposed.append(entry)
                else:
                    neutral.append(entry)

            all_opinions = [
                self.opinions[hid].get(topic, 0.0)
                for hid in self.households
            ]
            n = len(all_opinions) if all_opinions else 1
            avg_opinion = sum(all_opinions) / n

            consensus = 1.0 - (
                sum(abs(o - avg_opinion) for o in all_opinions) / n
            )

            if len(supportive) > len(opposed):
                dominant = "supportive"
            elif len(opposed) > len(supportive):
                dominant = "opposed"
            else:
                dominant = "divided"

            narratives[topic] = {
                "avg_opinion": round(avg_opinion, 4),
                "consensus_strength": round(consensus, 4),
                "supportive_count": len(supportive),
                "opposed_count": len(opposed),
                "neutral_count": len(neutral),
                "dominant_stance": dominant,
                "income_breakdown": self._income_breakdown(
                    supportive, opposed, neutral,
                ),
                "housing_type_breakdown": self._housing_type_breakdown(
                    supportive, opposed, neutral,
                ),
            }

        return narratives

    def _income_breakdown(
        self,
        supportive: list[dict[str, Any]],
        opposed: list[dict[str, Any]],
        neutral: list[dict[str, Any]],
    ) -> dict[str, dict[str, int]]:
        """Show which income bands lean which direction."""
        breakdown: dict[str, dict[str, int]] = {}
        for group, label in [
            (supportive, "supportive"),
            (opposed, "opposed"),
            (neutral, "neutral"),
        ]:
            for entry in group:
                band = entry["income_band"]
                breakdown.setdefault(
                    band,
                    {"supportive": 0, "opposed": 0, "neutral": 0},
                )
                breakdown[band][label] += 1
        return breakdown

    def _housing_type_breakdown(
        self,
        supportive: list[dict[str, Any]],
        opposed: list[dict[str, Any]],
        neutral: list[dict[str, Any]],
    ) -> dict[str, dict[str, int]]:
        """Show which housing types lean which direction."""
        breakdown: dict[str, dict[str, int]] = {}
        for group, label in [
            (supportive, "supportive"),
            (opposed, "opposed"),
            (neutral, "neutral"),
        ]:
            for entry in group:
                ht = entry["housing_type"]
                breakdown.setdefault(
                    ht,
                    {"supportive": 0, "opposed": 0, "neutral": 0},
                )
                breakdown[ht][label] += 1
        return breakdown


async def start_social_simulation(
    trigger_user_id: str,
    zip_code: str | None = None,
    income_band: str | None = None,
    max_rounds: int = 10,
    topics: list[str] | None = None,
) -> str:
    """Start a social simulation run. Returns the run_id."""
    run_id = str(uuid.uuid4())

    # Build household filter
    household_filter: dict[str, Any] = {}
    if zip_code:
        household_filter["zip_code"] = zip_code
    if income_band:
        household_filter["income_band"] = income_band

    # Create run record
    async with async_session() as db:
        run = SocialSimulationRun(
            id=run_id,
            trigger_user_id=trigger_user_id,
            household_filter=household_filter,
            total_rounds=max_rounds,
            topics=topics or TOPICS,
            status="preparing",
        )
        db.add(run)
        await db.commit()

    # Load households and edges
    async with async_session() as db:
        query = select(HouseholdProfile)
        if zip_code:
            query = query.where(
                HouseholdProfile.zip_code == zip_code,
            )
        if income_band:
            query = query.where(
                HouseholdProfile.income_band == income_band,
            )

        result = await db.execute(query)
        households = list(result.scalars().all())

        if not households:
            async with async_session() as db2:
                await db2.execute(
                    update(SocialSimulationRun)
                    .where(SocialSimulationRun.id == run_id)
                    .values(
                        status="failed",
                        error_message=(
                            "No households match the filter criteria."
                        ),
                    )
                )
                await db2.commit()
            return run_id

        # Load edges between these households
        household_ids = [cast(str, h.id) for h in households]
        edge_query = select(HouseholdSocialEdge).where(
            HouseholdSocialEdge.source_id.in_(household_ids),
            HouseholdSocialEdge.target_id.in_(household_ids),
        )
        edge_result = await db.execute(edge_query)
        edges = list(edge_result.scalars().all())

    # Create simulator and run in background
    simulator = SocialSimulator(
        run_id=run_id,
        trigger_user_id=trigger_user_id,
        households=households,
        edges=edges,
        topics=topics,
        max_rounds=max_rounds,
    )

    asyncio.create_task(_run_simulation_task(simulator, run_id))
    return run_id


async def _run_simulation_task(
    simulator: SocialSimulator, run_id: str,
) -> None:
    """Background task wrapper for simulation execution."""
    try:
        await simulator.run()
    except Exception as e:
        logger.error(
            "social_sim.task_failed",
            run_id=run_id,
            error=str(e),
            exc_info=True,
        )
        async with async_session() as db:
            await db.execute(
                update(SocialSimulationRun)
                .where(SocialSimulationRun.id == run_id)
                .values(status="failed", error_message=str(e))
            )
            await db.commit()
        _social_sims[run_id] = {
            "id": run_id,
            "status": "failed",
            "error": str(e),
        }
