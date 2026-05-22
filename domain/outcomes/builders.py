"""Phase F outcome projection builders.

Pure read-models that turn layered runtime inputs (offer history, listing
dates, reaction vectors) into observable outcome metrics. Every builder is a
deterministic, side-effect-free function that returns ``None`` (or a
sensible zero) when the input lacks signal — never raises.

Composition entry-point: :func:`build_outcome_snapshot`. Use the individual
builders directly when you only need one metric.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from domain.outcomes.projections import MarketOutcomeSnapshot, NegotiationOfferSnapshot
from domain.reactions.models import ReactionVector

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def project_price_movement(offers: list[NegotiationOfferSnapshot]) -> float | None:
    """Percentage delta from first to most recent offer price."""
    if len(offers) < 2:
        return None

    ordered = [
        offer for offer in offers if offer.offer_price is not None
    ]
    if len(ordered) < 2:
        return None

    first = float(ordered[0].offer_price)
    last = float(ordered[-1].offer_price)
    if first == 0:
        return None
    return (last - first) / first * 100.0


def project_time_on_market(
    listed_at: datetime | None,
    *,
    closed_at: datetime | None = None,
    now: datetime | None = None,
) -> int | None:
    """Days between listing and close (or now if still active)."""
    if listed_at is None:
        return None

    listed_at = _ensure_aware(listed_at)
    end = _ensure_aware(closed_at) if closed_at is not None else (now or _now_utc())
    delta = end - listed_at
    days = delta.days
    return max(0, days)


def project_offer_behavior(
    offers: list[NegotiationOfferSnapshot],
) -> dict[str, float | int]:
    """Summarize offer activity: volume + acceptance/rejection rates."""
    volume = len(offers)
    if volume == 0:
        return {
            "offer_volume": 0,
            "acceptance_rate": 0.0,
            "rejection_rate": 0.0,
            "withdrawal_rate": 0.0,
        }

    accepted = sum(1 for offer in offers if offer.status == "accepted")
    rejected = sum(1 for offer in offers if offer.status == "rejected")
    withdrawn = sum(1 for offer in offers if offer.status == "withdrawn")

    return {
        "offer_volume": volume,
        "acceptance_rate": accepted / volume,
        "rejection_rate": rejected / volume,
        "withdrawal_rate": withdrawn / volume,
    }


def project_concession_rate(
    asking_price: float | None,
    offers: list[NegotiationOfferSnapshot],
) -> float | None:
    """Percentage gap between asking price and most recent offer (positive = concession)."""
    if asking_price is None or asking_price <= 0 or not offers:
        return None

    latest = next(
        (offer for offer in reversed(offers) if offer.offer_price is not None),
        None,
    )
    if latest is None:
        return None

    return (asking_price - float(latest.offer_price)) / asking_price * 100.0


def project_permit_friction(
    reaction: ReactionVector,
    *,
    permit_signal: float | None = None,
) -> float | None:
    """Estimate permit friction from resistance + optional external signal.

    Returns a value in [0, 1]. Higher = more friction. If neither the reaction
    layer nor the signal carry meaningful data, returns ``None``.
    """
    has_signal = (
        reaction.resistance_to_development != 0.0
        or reaction.displacement_concern != 0.0
        or permit_signal is not None
    )
    if not has_signal:
        return None

    resistance = (reaction.resistance_to_development + 1.0) / 2.0
    displacement = (reaction.displacement_concern + 1.0) / 2.0
    base = 0.6 * resistance + 0.4 * displacement

    if permit_signal is not None:
        permit_signal = max(0.0, min(1.0, float(permit_signal)))
        base = 0.5 * base + 0.5 * permit_signal

    return max(0.0, min(1.0, base))


def project_neighborhood_sentiment(
    reactions: Iterable[ReactionVector],
) -> float | None:
    """Average normalized sentiment across reaction vectors. ``None`` if empty.

    Sentiment combines trust + safety + (1 - displacement) + willingness, mapped
    from the [-1, 1] reaction-variable space onto [0, 1].
    """
    samples: list[float] = []
    for reaction in reactions:
        components = [
            reaction.trust_in_trajectory,
            reaction.perceived_safety,
            -reaction.displacement_concern,
            reaction.willingness_to_transact,
        ]
        # Map each component from [-1, 1] -> [0, 1] and average.
        score = sum((value + 1.0) / 2.0 for value in components) / len(components)
        samples.append(max(0.0, min(1.0, score)))

    if not samples:
        return None
    return sum(samples) / len(samples)


def build_outcome_snapshot(
    *,
    listing_id: str | None = None,
    asking_price: float | None = None,
    offers: list[NegotiationOfferSnapshot] | None = None,
    listed_at: datetime | None = None,
    closed_at: datetime | None = None,
    reactions: list[ReactionVector] | None = None,
    permit_signal: float | None = None,
    turnover_rate: float | None = None,
) -> MarketOutcomeSnapshot:
    """Compose all builders into a :class:`MarketOutcomeSnapshot`.

    Lenient: any individual metric that can't be computed becomes ``None``;
    the snapshot is always returned. Existing callers can keep using
    :func:`merge_outcome_snapshot` to layer in additional fields later.
    """
    offers = offers or []
    reactions = reactions or []
    aggregate_reaction = (
        reactions[-1] if reactions else ReactionVector()
    )

    behavior = project_offer_behavior(offers)

    return MarketOutcomeSnapshot(
        listing_id=listing_id,
        price_change_pct=project_price_movement(offers),
        time_on_market_days=project_time_on_market(listed_at, closed_at=closed_at),
        offer_volume=int(behavior["offer_volume"]),
        concession_rate=project_concession_rate(asking_price, offers),
        turnover_rate=turnover_rate,
        permit_friction=project_permit_friction(
            aggregate_reaction,
            permit_signal=permit_signal,
        ),
        neighborhood_sentiment=project_neighborhood_sentiment(reactions),
    )


__all__ = [
    "build_outcome_snapshot",
    "project_concession_rate",
    "project_neighborhood_sentiment",
    "project_offer_behavior",
    "project_permit_friction",
    "project_price_movement",
    "project_time_on_market",
]
