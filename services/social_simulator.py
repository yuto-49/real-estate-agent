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
from domain.reactions.social_dynamics import (
    SOCIAL_REACTION_TOPICS,
    TOPIC_DESCRIPTIONS,
    build_initial_opinions,
    validate_topics,
)
from domain.reactions.runtime import SocialReactionRuntime
from services.logging import get_logger

logger = get_logger(__name__)

TOPICS = list(SOCIAL_REACTION_TOPICS)

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
        self.edges = edges
        self.topics = validate_topics(topics)
        self.max_rounds = max_rounds
        self.active_fraction = active_fraction

        # Track opinion state per household per topic
        initial_opinions: dict[str, dict[str, float]] = {}
        for household in households:
            household_id = cast(str, household.id)
            initial_opinions[household_id] = build_initial_opinions(household)
        self.runtime = SocialReactionRuntime(
            households=households,
            edges=edges,
            opinions=initial_opinions,
        )
        self.households: dict[str, HouseholdProfile] = self.runtime.households
        self.neighbors = self.runtime.neighbors
        self.opinions = self.runtime.opinions

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
        return self.runtime.select_active_households(self.active_fraction)

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
        return self.runtime.gather_neighbor_opinions(household_id, topic)

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
        """Apply the opinion drift formula."""
        return self.runtime.apply_opinion_drift(
            household,
            current=current,
            neighbor_opinions=neighbor_opinions,
            llm_delta=llm_delta,
        )

    def _compute_round_delta(self) -> float:
        """Compute average opinion change across all households."""
        return self.runtime.compute_round_delta(self._previous_opinions)

    def _compute_sentiment_delta(
        self, initial_opinions: dict[str, dict[str, float]],
    ) -> dict[str, dict[str, float]]:
        """Compute how opinions shifted from initial to final state."""
        return self.runtime.compute_sentiment_delta(
            initial_opinions=initial_opinions,
            topics=self.topics,
        )

    def _detect_narratives(self) -> dict[str, dict[str, Any]]:
        """Cluster households by opinion similarity per topic."""
        return self.runtime.detect_narratives(self.topics)

    def _income_breakdown(
        self,
        supportive: list[dict[str, Any]],
        opposed: list[dict[str, Any]],
        neutral: list[dict[str, Any]],
    ) -> dict[str, dict[str, int]]:
        """Show which income bands lean which direction."""
        return self.runtime._stance_breakdown(
            supportive,
            opposed,
            neutral,
            field_name="income_band",
        )

    def _housing_type_breakdown(
        self,
        supportive: list[dict[str, Any]],
        opposed: list[dict[str, Any]],
        neutral: list[dict[str, Any]],
    ) -> dict[str, dict[str, int]]:
        """Show which housing types lean which direction."""
        return self.runtime._stance_breakdown(
            supportive,
            opposed,
            neutral,
            field_name="housing_type",
        )


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
            topics=validate_topics(topics),
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
        topics=validate_topics(topics),
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
