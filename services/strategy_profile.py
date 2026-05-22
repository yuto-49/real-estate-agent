"""Strategy profile extractor — Phase S5.

Parses a user's free-text investing strategy or opinion into a structured
``StrategyProfile`` for review. The profile is fully defaulted so a sparse
description still produces a valid, editable form on the frontend — same
seed-then-confirm pattern as the Zillow listing prefill.

The extraction has two implementations:

* ``HeuristicStrategyExtractor`` (default) — deterministic keyword scan.
  Used in tests and as the fallback when no LLM client is wired.
* An LLM-backed extractor can be plugged in by passing any object that
  satisfies the ``StrategyExtractor`` Protocol to ``extract_strategy_profile``.
"""

from __future__ import annotations

import re
from typing import Protocol

from api.schemas import (
    StrategyAssumptions,
    StrategyPolicyConfig,
    StrategyProfile,
    StrategyThesis,
)


class StrategyExtractor(Protocol):
    """Pluggable seam — anything that produces a StrategyProfile from text."""

    async def extract(self, text: str) -> StrategyProfile | None: ...


# ── default profile + helpers ─────────────────────────────────────────


def default_strategy_profile() -> StrategyProfile:
    """Return the baseline profile used when no signal can be extracted."""
    return StrategyProfile()


_PCT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_YEAR_PATTERN = re.compile(r"(\d+)\s*[- ]?\s*(?:yr|year|yrs|years)\b", re.IGNORECASE)


def _find_pct_after(text: str, keywords: tuple[str, ...]) -> float | None:
    """Find an ``N%`` figure near any of the keywords.

    Searches the 40-char post-keyword window first (typical phrasing
    ``"rent growth of 4%"``) then falls back to the pre-keyword window
    (``"8% vacancy"``).
    """
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw)
        if idx == -1:
            continue
        post = text[idx + len(kw) : idx + len(kw) + 40]
        match = _PCT_PATTERN.search(post)
        if match:
            return float(match.group(1)) / 100.0
        pre = text[max(0, idx - 40) : idx]
        # Take the last percent in the pre-window — it's the closest to the keyword.
        matches = list(_PCT_PATTERN.finditer(pre))
        if matches:
            return float(matches[-1].group(1)) / 100.0
    return None


def _find_year_count(text: str, keywords: tuple[str, ...]) -> int | None:
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw)
        if idx == -1:
            continue
        window = text[max(0, idx - 40) : idx + len(kw) + 40]
        match = _YEAR_PATTERN.search(window)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
    return None


def _find_hold_years(text: str) -> int | None:
    """Detect the user's intended hold period.

    Tries keyword-proximity first (``"hold"``, ``"horizon"``), then falls
    back to "any N-year mention" when a hold/flip/exit verb is in the text.
    """
    by_kw = _find_year_count(text, ("hold", "horizon", "flip"))
    if by_kw is not None:
        return by_kw
    lower = text.lower()
    if any(k in lower for k in ("flip", "hold", "exit", "sell")):
        match = _YEAR_PATTERN.search(text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
    return None


def _detect_risk_tolerance(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ("low risk", "conservative", "cautious", "risk-averse")):
        return "low"
    if any(
        w in lower
        for w in ("high risk", "aggressive", "opportunistic", "high-risk")
    ):
        return "high"
    return "medium"


def _detect_outlook(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ("bullish", "rising", "gentrif", "growth")):
        return "bullish"
    if any(w in lower for w in ("bearish", "downturn", "soft", "decline")):
        return "bearish"
    return "neutral"


def _detect_trajectory(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ("displacement", "evict", "rent burden", "rent-burdened")):
        return "displacement_pressure"
    if any(w in lower for w in ("gentrif", "neighborhood trajectory", "upzon", "trending up")):
        return "neighborhood_trajectory"
    return "none"


_TOPIC_KEYWORDS = {
    "market_prices": ("price", "value", "appreciation"),
    "eviction_policy": ("evict", "tenant protection", "displacement"),
    "voucher_program": ("voucher", "section 8"),
    "neighborhood_safety": ("safety", "crime", "secure"),
}


def _detect_topics(text: str) -> list[str]:
    lower = text.lower()
    return [
        topic
        for topic, kws in _TOPIC_KEYWORDS.items()
        if any(kw in lower for kw in kws)
    ]


# ── heuristic extractor ───────────────────────────────────────────────


class HeuristicStrategyExtractor:
    """Deterministic keyword-based extractor.

    Used as the default when no LLM client is wired, and as the fallback
    when an LLM-backed extractor returns ``None``. Catches obvious signals
    (rent growth %, hold period, "buy and hold", "tenant protection",
    etc.) and falls back to defaults for everything else.
    """

    async def extract(self, text: str) -> StrategyProfile | None:
        if not text or not text.strip():
            return None

        lower = text.lower()

        rent_growth = _find_pct_after(text, ("rent growth", "rents grow", "rents rise"))
        expense_growth = _find_pct_after(text, ("expense growth", "opex growth", "expenses grow"))
        vacancy = _find_pct_after(text, ("vacancy",))
        hold_years = _find_hold_years(text)
        exit_cap = _find_pct_after(text, ("exit cap", "cap rate"))
        loan_outlook = _find_pct_after(text, ("loan rate", "mortgage rate", "rates rise to", "rates at"))

        assumptions = StrategyAssumptions(
            rent_growth=rent_growth if rent_growth is not None else 0.03,
            expense_growth=expense_growth if expense_growth is not None else 0.025,
            vacancy_rate=vacancy if vacancy is not None else 0.05,
            hold_period_years=hold_years if hold_years else 10,
            exit_cap_rate=exit_cap if exit_cap is not None else 0.07,
            loan_rate_outlook=loan_outlook,
        )

        sell_bias = 0.0
        raise_rent_bias = 0.0
        if any(w in lower for w in ("flip", "sell", "exit quickly", "short hold")):
            sell_bias = 0.4
        if any(w in lower for w in ("buy and hold", "buy-and-hold", "long term", "long-term")):
            sell_bias = -0.4
        if any(w in lower for w in ("raise rent", "push rent", "market rent")):
            raise_rent_bias = 0.4
        if any(w in lower for w in ("hold rent", "freeze rent", "tenant protection")):
            raise_rent_bias = -0.4

        policy = StrategyPolicyConfig(
            risk_tolerance=_detect_risk_tolerance(text),
            refi_rate_threshold=0.06,
            sell_bias=sell_bias,
            raise_rent_bias=raise_rent_bias,
            tenant_protection=any(
                w in lower for w in ("tenant protect", "protect tenant", "no displacement")
            ),
        )

        thesis = StrategyThesis(
            trajectory=_detect_trajectory(text),
            market_outlook=_detect_outlook(text),
            sentiment_topics=_detect_topics(text),
            notes=text.strip()[:500] if text.strip() else None,
        )

        return StrategyProfile(
            assumptions=assumptions, policy_config=policy, thesis=thesis
        )


_DEFAULT_EXTRACTOR = HeuristicStrategyExtractor()


async def extract_strategy_profile(
    text: str, *, extractor: StrategyExtractor | None = None
) -> StrategyProfile:
    """Extract a profile from free text — LLM if wired, heuristic otherwise.

    Always returns a fully-defaulted ``StrategyProfile``. Empty text yields
    the baseline profile (the user can override every field).
    """
    if not text or not text.strip():
        return default_strategy_profile()

    chosen = extractor or _DEFAULT_EXTRACTOR
    try:
        profile = await chosen.extract(text)
    except Exception:
        profile = None

    if profile is None and extractor is not None:
        # Injected extractor declined — fall back to the heuristic.
        try:
            profile = await _DEFAULT_EXTRACTOR.extract(text)
        except Exception:
            profile = None

    return profile or default_strategy_profile()
