# domain/ — Layered Domain Runtime

## Purpose
Pure-Python, side-effect-free, deterministic business logic organized as a five-layer pipeline: market signals -> actor/cohort signals -> reaction vectors -> decisions -> outcomes -> reports. No DB, Redis, or Claude API calls allowed here.

## Subdirectories

| Path | Layer | Key Types |
|------|-------|-----------|
| `market/` | Market context | `MarketContextSnapshot`, market events |
| `actors/` | Actor/cohort signals | `ActorSignalState`, `CohortSignalState`, `ActorType` |
| `reactions/` | Reaction vectors | `ReactionVector`, `ReactionEvent`, `ReactionEngine`, narrative clustering |
| `decisions/` | Decision policies | `DecisionContext`, `DecisionRuntime`, negotiation/list-hold/lease/churn/dev-resistance policies |
| `outcomes/` | Market projections | `MarketOutcomeSnapshot`, `NegotiationOfferSnapshot` |
| `reports/` | Report artifacts | `UnderwritingReport`, `NegotiationBriefing`, `PolicyRiskBrief`, `ReplayNarrative` |

## Key Files

| File | Role |
|------|------|
| `events.py` | Canonical event taxonomy with `EventNamespace`, `canonical_event()`, lenient registry |

## Critical Rules
1. **Pure functions only** — no I/O, no database, no network, no side effects
2. **Deterministic** — same inputs always produce same outputs
3. **Lenient** — missing/unknown data logs a warning and returns a sensible default; never raises (except negotiation state machine `ValueError`)
4. **Frozen dataclasses** — all output types are immutable

## Dependencies
- None (pure Python, stdlib only)
- Consumed by `services/` and `api/` for persistence and orchestration
