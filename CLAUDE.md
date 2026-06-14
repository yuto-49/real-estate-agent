# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent real estate negotiation platform with social behavior simulation, intelligence pipeline, and workforce housing analysis. FastAPI backend + React frontend + Claude API agents.

**Domain focus:** Workforce housing — affordable, accessible housing for essential workers and moderate-income households, with emphasis on regulatory compliance and community-driven intelligence.

## Quick Commands

```bash
# Infrastructure
docker compose -f ~/docker-shared-services.yml up -d postgres redis
bash scripts/init-shared-db.sh

# Backend
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_properties.py
uvicorn main:app --reload          # http://localhost:8000

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:5173

# Tests
pytest tests/ -v                   # 585 tests, in-memory SQLite, no Docker needed
pytest tests/ --cov=. --cov-report=term-missing
pytest tests/test_signal_providers.py -v               # single file
pytest tests/test_market_state.py::test_build_snapshot_populates_property_context  # single test

# Market signals (Phase M1/M2 tooling — see doc/market-signal-sources.md)
python scripts/backfill_market_signals.py              # derive from properties table
python scripts/fetch_external_signals.py --list        # registered providers
python scripts/fetch_external_signals.py --source mock # write external signals

# Dev auth account (after .env has Supabase keys set)
python scripts/create_dev_user.py
```

## Architecture at a Glance

```
User/Frontend → FastAPI API → Orchestrator → Claude Agents (buyer/seller/broker/assistant)
                    ↓                              ↓
              PostgreSQL + Redis          Tool Execution (ACL-enforced)
                    ↓                              ↓
              Domain Events ←────────── Guardrails + Business Rules
                    ↓
             Redis Pub/Sub → WebSocket → React Frontend

Layered Domain Runtime (domain/, pure-Python projections, no I/O):
  Market signals → Actor/Cohort signals → Reaction vectors → Decision recommendations
                                                           → Outcome snapshots
                                                           → Reports + Replay narratives

Social Simulation (legacy loop, additive — being repositioned):
  Synthetic Households → Social Graph → Opinion Rounds → Narrative Clusters → MiroFish Report → Negotiation
```

## Key Directories

| Path | Purpose |
|------|---------|
| `agent/` | Multi-agent system: base agent, buyer/seller/broker/assistant, orchestrator, negotiation engine, tool ACL, prompts v2.0.0 |
| `agent/tools/` | Tool handlers: search, neighborhood, offers, listings, comps, counter, broker, intelligence |
| `api/` | FastAPI routers: properties, offers, users, negotiations, reports, simulation, batch, webhooks, ws, **portfolio (+ `/summary`), underwrite + listing/parse, decisions, strategy** (investor + strategy-run surfaces) |
| `api/schemas.py` | All Pydantic request/response models |
| `db/models.py` | 23 SQLAlchemy models incl. UserProfile (+ `preferred_mode`), Property, Offer, Negotiation, AgentDecision, AgentMemory, MiroFishReport, MiroFishSeed, SimulationResult, DomainEvent, MarketSignal, HouseholdProfile, HouseholdSocialEdge, SocialSimulationRun, MarketSimulationRun, **InvestorPortfolio, PortfolioHolding, HoldingFinancials, UnderwritingScenario** |
| `domain/` | Layered domain runtime — pure-Python projections, no I/O. See "Layered Domain Runtime" section |
| `domain/events.py` | Canonical event taxonomy (lenient registry, namespace enums) |
| `domain/market/` | `MarketContextSnapshot` model + market events |
| `domain/actors/` | `ActorSignalState`, `CohortSignalState`, `ActorType`, household/user signal projections |
| `domain/reactions/` | `ReactionVector`, `ReactionEvent`, `ReactionEngine`, narrative clustering, convergence, vector distance |
| `domain/decisions/` | Negotiation state machine + `DecisionRuntime` with pluggable policies (negotiation, list/hold, lease, churn, dev-resistance). **Wired to a live consumer** via `api/decisions.py` (`GET /api/decisions/holding/{id}`) |
| `domain/outcomes/` | `MarketOutcomeSnapshot` + builders (price movement, time-on-market, offer behavior, concession, permit friction, sentiment) |
| `domain/reports/` | Report artifacts (`UnderwritingReport`, `NegotiationBriefing`, `PolicyRiskBrief`) + replay engine (`ReplayFrame`, `ReplayNarrative`) |
| `services/` | Business logic: event store, negotiation simulator, batch simulator, persona generator, scenario variants, maps, market data, Redis, pub/sub, metrics, job queue, `market_state.build_snapshot`, `signal_writer.upsert_signal` (shared idempotent-per-day writer), **`holding_decision.compute_holding_decision`** (extracted from `api/decisions.py`), **`portfolio_summary.build_portfolio_summary`** (the `/summary` aggregator and strategy-run analysis seed), **`strategy_profile.extract_strategy_profile`** (free-text → `StrategyProfile`, LLM-pluggable, heuristic fallback), **`strategy_runner`** (in-process strategy-run store + `execute_strategy_run`), **`unified_report.reconcile_unified_report`** (analysis vs simulation reconciliation) |
| `services/signal_providers/` | Pluggable external market-signal providers (`MarketSignalProvider` Protocol, `ReinfolibTransactionProvider`, `ReinfolibLandPriceProvider`, `ReinfolibAppraisalProvider`, `ReinfolibHazardProvider`, `EStatProvider`, registry). See `doc/market-signal-sources.md` |
| `services/tenant_pool.py` | Income-band-aware tenant-pool query over `HouseholdProfile` + neighborhood trajectory presets for the social simulator |
| `intelligence/` | MiroFish pipeline: seed assembly, HTTP client (circuit breaker + retry), financial models (Monte Carlo, cash flow, tax), report parser. **+ investor analytics: `underwriting.py` (cap rate / CoC / DSCR / IRR), `tax_basic.py`, `stress_test.py` (Monte Carlo stress test)** |
| `middleware/` | Correlation ID, **Supabase JWT verification** (`middleware/auth.py` — RS256 via JWKS), rate limiting |
| `frontend/src/` | React 18 + TypeScript + Vite: 8 pages (lazy-loaded) incl. **`PortfolioPage.tsx`** (investor surface, **6 tabs — Overview (default) / Holdings / Underwrite / Stress Test / Decisions / Strategy** + `components/portfolio/`), typed WebSocket, **Supabase auth (`hooks/useAuth.ts`, `pages/SignInPage.tsx`, `utils/supabase.ts`); `api.ts` injects Bearer token**. Vitest unit tests + Playwright E2E (`npm run test` / `test:e2e`) |
| `frontend/src/pages/NegotiationPage.tsx` | **Persona Risk Workspace** — primary surface for the social-simulation flow. Drives `/api/social-sim/*` to project how synthetic households (trigger user × zip × income band × topics) shift stance and sentiment per round. Still hosts the legacy negotiation session machinery (offer ledger, typed actions, event replay) for downstream callers, but the social-sim panel is the dominant surface |
| `scripts/` | DB init, seeds, `backfill_market_signals.py`, `fetch_external_signals.py`, `create_dev_user.py` |
| `doc/` | Architecture docs, `agent-architecture.md` (multi-agent runtime walkthrough), `market-signal-sources.md`, `SUPABASE_AUTH_SETUP.md`, testing guide |
| `tests/` | 585 pytest tests (in-memory SQLite, fakeredis, no external services) |

## Database

- **Engine:** PostgreSQL with asyncpg (async SQLAlchemy 2.0)
- **Migrations:** Alembic with async engine
- **Connection:** `postgresql+asyncpg://dev:dev@localhost:5432/realestate`
- **Testing:** In-memory SQLite with JSONB→JSON patching, mocked Redis

## Critical Patterns — Follow These

1. **Event Sourcing:** All state changes must write to `domain_events` table with correlation ID. Never mutate state without an event.
2. **Tool ACL:** Agent tools are gated by a frozen permission map (`agent/tool_acl.py`). Never bypass. Validated pre- and post-Claude API call.
3. **Guardrails:** Hard-coded business rules in `agent/guardrails.py`. Offers must be >= 50% of asking price. Max deal value auto-approved: $2M.
4. **Async-first:** All DB, Redis, HTTP, and Claude API calls must be async. Use `asyncio.Semaphore` for concurrency control.
5. **Provider Pattern:** Market data and maps use Protocol-based providers (mock + real). Always support both modes.
6. **Circuit Breaker:** External service calls (MiroFish, TomTom) use tenacity retry + circuit breaker. 3 retries, exponential backoff, circuit opens after 5 failures.
7. **Correlation IDs:** Every request gets a UUID via middleware. Thread it through logs, events, and agent decisions.
8. **Layered domain runtime is pure:** Code under `domain/` must be side-effect free, deterministic, no DB / Redis / Claude calls. Projections take inputs, return frozen dataclasses. Persistence and orchestration live in `services/` and `api/`.
9. **Lenient projections:** Builders and runtimes in `domain/` log a warning and return a sensible default on missing/unknown data — never raise. `ValueError` is reserved for actual transitions in the negotiation state machine.
10. **Market-signal writes go through `services.signal_writer.upsert_signal`** — same-calendar-day writes for a given `(signal_type, subject_type, subject_id)` update in place; different day inserts. Never `db.add(MarketSignal(...))` directly from new code.
11. **External providers must inject `httpx.AsyncClient`** so tests can use `httpx.MockTransport`. No live HTTP calls in unit tests. Live integration tests, if added, go under `tests/integration/` and are skipped by default.

## Configuration

All config via `config.py` (pydantic-settings) reading from `.env`:

| Variable | Default | Notes |
|----------|---------|-------|
| `ANTHROPIC_API_KEY` | (empty) | Required for agent conversations |
| `DATABASE_URL` | `postgresql+asyncpg://dev:dev@localhost:5432/realestate` | |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `MIROFISH_MODE` | `mock` | `mock` or `live` |
| `MARKET_DATA_PROVIDER` | `mock` | `mock` |
| `MAX_SIMULATION_ROUNDS` | `30` | Negotiation simulation cap |
| `MAX_BATCH_SCENARIOS` | `6` | Batch simulation limit |
| `MONTE_CARLO_SCENARIOS` | `300` | Financial model iterations |
| `SUPABASE_URL` | (empty) | Supabase project URL (also exposed to frontend as `VITE_SUPABASE_URL`) |
| `SUPABASE_ANON_KEY` | (empty) | Public anon key for frontend (`VITE_SUPABASE_ANON_KEY`) |
| `SUPABASE_SERVICE_ROLE_KEY` | (empty) | Server-only — `scripts/create_dev_user.py` and any admin ops |
| `SUPABASE_JWT_ISSUER` | (empty) | Expected `iss` claim, e.g. `https://<project>.supabase.co/auth/v1` |
| `SUPABASE_JWKS_URL` | (empty) | JWKS endpoint for RS256 key fetch in `middleware/auth.py` |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | Expected `aud` claim |

> Auth middleware is **disabled** (passthrough) when `SUPABASE_JWT_ISSUER`/`SUPABASE_JWKS_URL` are empty — useful for tests and bare-DB dev. Set both to enable verification. See `doc/SUPABASE_AUTH_SETUP.md`.

## Social Simulation — Persona Risk Workspace

The social simulator is the **risk-assessment surface** for the platform. It
projects how different synthetic personas (households filtered by zip,
income band, demographic) would shift stance and sentiment in response to a
trigger event across a configurable topic set (price moves, displacement,
gentrification, transit, school changes, eviction risk).

**Frontend entry point:** `/negotiate` route → `NegotiationPage.tsx` → the
"Social Interaction Simulation" panel. The panel is now the dominant
workspace on that route; the legacy negotiation-session UI sits alongside it
for downstream callers but is no longer the page's primary purpose.

**Backend pieces** (see `SOCIAL_SIMULATION_IMPLEMENTATION.md` for full plan):

- **HouseholdProfile** model with opinion fields (sentiment, policy support, satisfaction, influence, communication style)
- **HouseholdSocialEdge** model for social graph (neighbor, income peer, language peer, demographic edges)
- **SocialSimulationRun** + **SocialSimulationAction** models for tracking simulation state
- **SocialSimulator** engine: opinion rounds with Claude API, convergence detection, narrative clustering
- **Social Report Bridge:** translates simulation output → MiroFishReport format for seamless integration with existing negotiation pipeline
- **API:** `POST /api/social-sim/start`, `GET .../status`, `GET .../result`, `GET .../actions`, `GET .../timeline`, `POST .../generate-report`

> The legacy `services/social_simulator.py` loop is intentionally untouched.
> The new layered runtime under `domain/` is the additive primitive that newer
> features should target. Migration is opt-in: callers can mix and match.

## Layered Domain Runtime

The `domain/` package implements a five-layer pipeline (Phases A–G of the
roadmap, all complete). Every layer is **pure-Python**, **side-effect free**,
**deterministic**, and **lenient** (missing data → `None` or warning, never raises).

| Layer | Module | Primary Types |
|---|---|---|
| Event taxonomy | `domain/events.py` | `EventNamespace`, `MARKET_EVENTS`, `canonical_event()` |
| Market | `domain/market/` | `MarketContextSnapshot`, `market_event()` |
| Actor / cohort | `domain/actors/` | `ActorSignalState`, `CohortSignalState`, `infer_actor_type()`, `user_profile_signals()`, `cohort_signals()` |
| Reaction | `domain/reactions/` | `ReactionVector`, `ReactionEvent`, `ReactionEngine`, `extract_narratives()`, `vector_distance()` |
| Decision | `domain/decisions/` | `DecisionContext`, `DecisionRuntime`, `NegotiationPolicy`, `ListHoldPolicy`, `LeasePolicy`, `ChurnPolicy`, `DevResistancePolicy`, `default_policies()` |
| Outcome | `domain/outcomes/` | `MarketOutcomeSnapshot`, `build_outcome_snapshot()`, `project_*()` |
| Report / replay | `domain/reports/` | `UnderwritingReport`, `NegotiationBriefing`, `PolicyRiskBrief`, `ReplayNarrative`, `replay_reactions()` |

**Persistence boundary:** only `db/models.py::MarketSignal` was added (Phase B
migration `e1f8a9c4d572`). All other layers are computed read-models — store
them via existing `domain_events`/projection tables when callers need durability.

**Service-layer bridge:** `services/market_state.py::build_snapshot(db, property_id)`
is the only async entry point that pulls `MarketSignal` rows from PostgreSQL
and produces a `MarketContextSnapshot` for downstream layers. Neighborhood
signals are looked up under both `neighborhood_id` and `zip_code` —
property-level signals win, then the first neighborhood key that resolves.

## Market Signal Adoption (Phases M1/M2 — shipped)

The layered runtime is in place and now has live consumers: the investor
underwriting + decision surface reads signals via `services/market_state.py`
and `api/decisions.py`. Tooling and providers shipped so far:

| Piece | Path | Purpose |
|---|---|---|
| Backfill (in-DB) | `scripts/backfill_market_signals.py` | Derives `median_sale_price` + `inventory_pressure` per zip and `hazard` per property from existing rows |
| External fetch CLI | `scripts/fetch_external_signals.py` | `--source <name>` runs one provider, upserts via the shared writer |
| Shared writer | `services/signal_writer.py::upsert_signal` | Idempotent **per calendar day** — same-day re-run updates the row; different day inserts a new one |
| Provider Protocol | `services/signal_providers/base.py` | `MarketSignalProvider` (name, async fetch) + frozen `ExternalSignal` DTO |
| Mock provider | `services/signal_providers/mock.py` | Deterministic Chicago zip fixture — no network |
| Chicago Crime | `services/signal_providers/chicago_crime.py` | Real, **no API key required** — SODA `ijzp-q8t2` → `safety_score` per zip |
| HUD FMR | `services/signal_providers/hud_fmr.py` | Fair Market Rent → `median_rent` per zip (API key in `.env`) |
| FRED | `services/signal_providers/fred.py` | Federal Reserve mortgage rate → `loan_rate` signal |
| FEMA NFHL | `services/signal_providers/fema_nfhl.py` | National Flood Hazard Layer → `hazard` flags per property |
| Census ACS | `services/signal_providers/census_acs.py` | American Community Survey → `median_rent` + `median_sale_price` per zip |
| Read API | `GET /api/properties/{id}/market-context` | Wraps `build_snapshot`, returns `MarketContextSnapshot` JSON |

Adding a new provider = ~50 lines: implement the Protocol, register in
`services/signal_providers/registry.py::_FACTORIES`, mock the HTTP call with
`httpx.MockTransport` in tests. See `doc/market-signal-sources.md` for the
catalog of candidate sources.

## Negotiation State Machine

```
IDLE → OFFER_PENDING → COUNTER_PENDING → ... → ACCEPTED → CONTRACT_PHASE → INSPECTION → CLOSING → CLOSED
                                                         ↗
                                          REJECTED / WITHDRAWN / ESCALATED
```

- Round 5+: ZOPA detection (spread <= 3% → suggest midpoint)
- Round 5+ with spread > 10%: auto-broker mediation
- Round 10+: auto-escalation
- Deadlines: 48h offers, 72h contracts, 10d inspection, 30d closing

## Testing Conventions

- All tests in `tests/` using pytest-asyncio
- In-memory SQLite, no external services required
- Mock Redis via fakeredis
- No real API calls in tests
- Run `pytest tests/ -v` before committing

## Coding Conventions

- Python 3.11+, type hints throughout
- Pydantic v2 for schemas, pydantic-settings for config
- SQLAlchemy 2.0 async style (select(), async_session)
- structlog for logging (never use print)
- FastAPI dependency injection for DB sessions
- UUID primary keys on all models
- JSONB columns for flexible structured data (disclosures, payloads, snapshots)
