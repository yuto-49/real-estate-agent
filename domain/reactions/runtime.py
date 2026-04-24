"""Reusable social reaction runtime helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from domain.reactions.social_dynamics import communication_style_multiplier


class SocialReactionRuntime:
    """Stateful helper for graph traversal, drift, and narrative projections."""

    def __init__(
        self,
        *,
        households: list[Any],
        edges: list[Any],
        opinions: dict[str, dict[str, float]],
    ):
        self.households: dict[str, Any] = {
            str(household.id): household for household in households
        }
        self.neighbors: defaultdict[str, list[tuple[str, float, str]]] = defaultdict(list)
        for edge in edges:
            source_id = str(edge.source_id)
            target_id = str(edge.target_id)
            edge_weight = float(edge.edge_weight)
            edge_type = str(edge.edge_type)
            self.neighbors[source_id].append((target_id, edge_weight, edge_type))
            self.neighbors[target_id].append((source_id, edge_weight, edge_type))

        self.opinions = opinions

    def select_active_households(
        self,
        active_fraction: float,
        *,
        rng: Any | None = None,
    ) -> list[str]:
        """Select households to activate for a round."""
        import random as random_module

        random_source = rng or random_module
        all_ids = list(self.households.keys())
        n_active = max(1, int(len(all_ids) * active_fraction))

        weights: list[float] = []
        for household_id in all_ids:
            household = self.households[household_id]
            weight = float(getattr(household, "influence_weight", 0.0) or 0.0)
            weight *= communication_style_multiplier(
                getattr(household, "communication_style", None)
            )
            weights.append(weight)

        total = sum(weights)
        if total == 0:
            return random_source.sample(all_ids, min(n_active, len(all_ids)))

        normalized_weights = [weight / total for weight in weights]
        selected: set[str] = set()
        attempts = 0
        while len(selected) < n_active and attempts < n_active * 3:
            selected.add(random_source.choices(all_ids, weights=normalized_weights, k=1)[0])
            attempts += 1
        return list(selected)

    def gather_neighbor_opinions(
        self,
        household_id: str,
        topic: str,
    ) -> list[dict[str, Any]]:
        """Gather weighted neighbor opinions for a topic."""
        result: list[dict[str, Any]] = []
        for neighbor_id, weight, edge_type in self.neighbors.get(household_id, []):
            if neighbor_id not in self.opinions:
                continue
            neighbor = self.households.get(neighbor_id)
            if not neighbor:
                continue
            style = getattr(neighbor, "communication_style", None)
            result.append(
                {
                    "id": neighbor_id,
                    "opinion": self.opinions[neighbor_id].get(topic, 0.0),
                    "weight": weight,
                    "edge_type": edge_type,
                    "income_band": str(getattr(neighbor, "income_band", "unknown")),
                    "communication_style": getattr(style, "value", style or "passive"),
                }
            )
        return result

    def apply_opinion_drift(
        self,
        household: Any,
        *,
        current: float,
        neighbor_opinions: list[dict[str, Any]],
        llm_delta: float,
    ) -> float:
        """Apply the opinion drift formula and clamp to the signed range."""
        stability = float(getattr(household, "opinion_stability", 0.5) or 0.5)
        if neighbor_opinions:
            total_weight = sum(neighbor["weight"] for neighbor in neighbor_opinions)
            if total_weight > 0:
                peer_avg = (
                    sum(neighbor["opinion"] * neighbor["weight"] for neighbor in neighbor_opinions)
                    / total_weight
                )
            else:
                peer_avg = current
        else:
            peer_avg = current

        new_opinion = (stability * current) + ((1 - stability) * peer_avg) + (0.1 * llm_delta)
        return round(max(-1.0, min(1.0, new_opinion)), 4)

    def compute_round_delta(
        self,
        previous_opinions: dict[str, dict[str, float]],
    ) -> float:
        """Compute average opinion change across all tracked topics."""
        if not previous_opinions:
            return 1.0

        total_delta = 0.0
        count = 0
        for household_id, previous_topics in previous_opinions.items():
            for topic, previous_value in previous_topics.items():
                current_value = self.opinions.get(household_id, {}).get(topic, previous_value)
                total_delta += abs(current_value - previous_value)
                count += 1
        return total_delta / count if count > 0 else 0.0

    def compute_sentiment_delta(
        self,
        *,
        initial_opinions: dict[str, dict[str, float]],
        topics: list[str],
    ) -> dict[str, dict[str, float]]:
        """Compute topic-level shifts between initial and current opinion state."""
        delta: dict[str, dict[str, float]] = {}
        for topic in topics:
            initial_values = [initial_opinions[household_id].get(topic, 0.0) for household_id in self.households]
            final_values = [self.opinions[household_id].get(topic, 0.0) for household_id in self.households]

            count = len(initial_values) if initial_values else 1
            initial_avg = sum(initial_values) / count
            final_avg = sum(final_values) / count
            volatility = sum(abs(final - initial) for final, initial in zip(final_values, initial_values)) / count

            delta[topic] = {
                "initial_avg": round(initial_avg, 4),
                "final_avg": round(final_avg, 4),
                "shift": round(final_avg - initial_avg, 4),
                "volatility": round(volatility, 4),
            }
        return delta

    def detect_narratives(self, topics: list[str]) -> dict[str, dict[str, Any]]:
        """Cluster households by opinion similarity for each topic."""
        narratives: dict[str, dict[str, Any]] = {}
        for topic in topics:
            supportive: list[dict[str, Any]] = []
            opposed: list[dict[str, Any]] = []
            neutral: list[dict[str, Any]] = []

            for household_id, topic_opinions in self.opinions.items():
                opinion_value = topic_opinions.get(topic, 0.0)
                household = self.households[household_id]
                entry = {
                    "id": household_id,
                    "opinion": opinion_value,
                    "income_band": str(getattr(household, "income_band", "unknown")),
                    "housing_type": str(getattr(household, "housing_type", "unknown")),
                    "influence": float(getattr(household, "influence_weight", 0.0) or 0.0),
                }
                if opinion_value > 0.2:
                    supportive.append(entry)
                elif opinion_value < -0.2:
                    opposed.append(entry)
                else:
                    neutral.append(entry)

            all_opinions = [self.opinions[household_id].get(topic, 0.0) for household_id in self.households]
            count = len(all_opinions) if all_opinions else 1
            avg_opinion = sum(all_opinions) / count
            consensus_strength = 1.0 - (
                sum(abs(opinion - avg_opinion) for opinion in all_opinions) / count
            )

            if len(supportive) > len(opposed):
                dominant_stance = "supportive"
            elif len(opposed) > len(supportive):
                dominant_stance = "opposed"
            else:
                dominant_stance = "divided"

            narratives[topic] = {
                "avg_opinion": round(avg_opinion, 4),
                "consensus_strength": round(consensus_strength, 4),
                "supportive_count": len(supportive),
                "opposed_count": len(opposed),
                "neutral_count": len(neutral),
                "dominant_stance": dominant_stance,
                "income_breakdown": self._stance_breakdown(
                    supportive,
                    opposed,
                    neutral,
                    field_name="income_band",
                ),
                "housing_type_breakdown": self._stance_breakdown(
                    supportive,
                    opposed,
                    neutral,
                    field_name="housing_type",
                ),
            }
        return narratives

    def _stance_breakdown(
        self,
        supportive: list[dict[str, Any]],
        opposed: list[dict[str, Any]],
        neutral: list[dict[str, Any]],
        *,
        field_name: str,
    ) -> dict[str, dict[str, int]]:
        breakdown: dict[str, dict[str, int]] = {}
        for group, label in (
            (supportive, "supportive"),
            (opposed, "opposed"),
            (neutral, "neutral"),
        ):
            for entry in group:
                field_value = entry[field_name]
                breakdown.setdefault(
                    field_value,
                    {"supportive": 0, "opposed": 0, "neutral": 0},
                )
                breakdown[field_value][label] += 1
        return breakdown
