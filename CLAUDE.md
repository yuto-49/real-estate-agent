# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tokyo workforce-housing **investor analytics** platform: portfolio underwriting,
market-signal intelligence, and forward strategy simulation. FastAPI backend +
React frontend + Claude API (used for listing analysis and free-text → structured
extraction, not conversation).

**Domain focus:** Workforce housing — affordable, accessible housing for essential
workers and moderate-income households, with emphasis on regulatory compliance and
market-signal-driven intelligence.

> **Post-pivot scope (important).** The earlier buyer/seller **negotiation chat**,
> social-sentiment **NIMBY simulator**, synthetic **market-tick engine**, and the
> **MiroFish** free-text report flow were **removed** (Alembic migration
> `f9a1b2c3d4e5` dropped their 15 tables; the frontend surface and dead schemas were
> removed afterward). The **layered domain runtime** and **market-signal pipeline**
> they seeded remain and now power the investor surface. Old docs
> (`SOCIAL_SIMULATION_IMPLEMENTATION.md`, parts of `architecture.md`) still describe
> the removed features and are stale.

## Quick Commands

```bash
# Infrastructure
docker compose -f ~/docker-shared-services.yml up -d postgres redis
bash scripts/init-shared-db.sh

# Backend
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_properties.py        # or seed_tokyo.py / seed_kaggle_usa.py / seed_from_csv.py
python scripts/seed_dev_portfolio.py     # demo investor portfolio + holdings
uvicorn main:app --reload                # http://localhost:8000

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
cd frontend && npm run test                 # Vitest unit tests
cd frontend && npm run test:e2e             # Playwright E2E

# Tests (backend)
pytest tests/ -v                   # ~347 tests, in-memory SQLite, no Docker needed
pytest tests/ --cov=. --cov-report=term-missing
pytest tests/test_signal_providers.py -v                                   # single file
pytest tests/test_strategy_events.py::test_execute_strategy_run_writes_started_and_completed_events  # single test

# Market signals (see doc/market-signal-sources.md)
python scripts/backfill_market_signals.py              # derive from properties table
python scripts/fetch_external_signals.py --list        # registered providers
python scripts/fetch_external_signals.py --source mock # write external signals

# Dev auth account (after .env has Supabase keys set)
python scripts/create_dev_user.py
```

## Architecture at a Glance

```
React frontend ──▶ FastAPI API (api/) ──▶ services/  (portfolio_summary, strategy_runner,
   (Portfolio        │                       holding_decision, market_state, signal_writer,
    page = the       │                       portfolio_chat_extractor, listing_import)
    center of        ▼                         │
    gravity)   PostgreSQL + Redis              ▼
                     │              domain/ — pure projections (no I/O):
                     │              market → actor → reaction → decision → outcome → report
                     ▼
            domain_events (event-sourced audit, correlation id)
            Redis pub/sub (live strategy-run step events)

Claude API: agent/analyst_council (listing-analysis council) +
            api/portfolio chat-import extraction.  services/strategy_profile is
            heuristic today (LLM-pluggable).
```

## Key Directories

| Path | Purpose |
|------|---------|
| `agent/` | `analyst_council.py` — Claude-driven listing-analysis council (multi-persona review) + `analyst_personas.py`. (The old buyer/seller/broker multi-agent negotiation system was removed.) |
| `api/` | FastAPI routers (all mounted in `main.py`): `properties` (+ `GET /{id}/market-context`), `search`, `users`, `portfolio` (+ `/summary`, `/aggregate`, holdings CRUD, CSV/chat import, `from-property`), `underwrite` (+ `/stress-test`, `listing/parse`), `listing`, `decisions` (`/holding/{id}`), `strategy` (extract / run / status / result / recent), `onboarding`, `investor-profile`, `config` (public), `listings` (listing-analysis) |
| `api/schemas.py` | All Pydantic v2 request/response models |
| `db/models.py` | 9 SQLAlchemy models + 10 enums: `UserProfile`, `Property`, `DomainEvent`, `MarketSignal`, `InvestorPortfolio`, `PortfolioHolding`, `HoldingFinancials`, `InvestorProfile`, `UnderwritingScenario` |
| `domain/` | Layered domain runtime — pure-Python projections, no I/O. See "Layered Domain Runtime" |
| `domain/events.py` | Canonical event taxonomy (lenient registry, namespace enums) |
| `domain/market/` | `MarketContextSnapshot` model + market events |
| `domain/actors/` | `ActorSignalState`, `CohortSignalState`, `ActorType`, `infer_actor_type()`, `user_profile_signals()`, `cohort_signals()` |
| `domain/reactions/` | `ReactionVector`, `ReactionEngine`, narrative clustering, convergence, `vector_distance()`, `derive.py` reaction-event builders |
| `domain/decisions/` | `DecisionRuntime` + pluggable policies (list/hold, lease, churn, dev-resistance, negotiation) — **live consumer** is `services/holding_decision.py` → `api/decisions.py`. `negotiation.py` is a dormant state-machine primitive (no product consumer) |
| `domain/outcomes/` | `MarketOutcomeSnapshot` + builders (price movement, time-on-market, offer behavior, concession, permit friction, sentiment) |
| `domain/reports/` | Report artifacts + replay engine (`ReplayFrame`, `ReplayNarrative`) |
| `services/` | Business logic + I/O. Investor stack: `portfolio_summary.build_portfolio_summary` (the `/summary` aggregator + strategy analysis seed), `strategy_runner` (in-process run store, `execute_strategy_run`, pure `project_simulation`), `unified_report.reconcile_unified_report`, `strategy_profile.extract_strategy_profile` (free-text → `StrategyProfile`, heuristic, LLM-pluggable), `holding_decision.compute_holding_decision`, `portfolio_chat_extractor`, `listing_import`. Platform: `event_store` (the only `domain_events` writer), `market_state.build_snapshot`, `signal_writer.upsert_signal` (shared idempotent-per-day writer), `market_data`/`market_data_provider`, `maps`, `redis`, `pubsub`, `metrics`, `job_queue`, `property_recommender`, `user_resolve`, JP helpers (`address_jp`, `money_jp`, `geocache`) |
| `services/signal_providers/` | Pluggable external market-signal providers (`MarketSignalProvider` Protocol, `MockSignalProvider`, `ChicagoCrimeProvider`, `HudFmrProvider`, `FredMortgageRateProvider`, `FemaNfhlProvider`, `CensusAcsProvider`, registry). See `doc/market-signal-sources.md` |
| `intelligence/` | Investor analytics: `underwriting.py` (cap rate / CoC / DSCR / IRR), `tax_basic.py`, `depreciation_jp.py` (JP depreciation schedule, consumed by `strategy_runner`), `stress_test.py` (Monte Carlo). `financial_models.py` is legacy/unreferenced |
| `middleware/` | `correlation.py` (correlation-id contextvar), `auth.py` (Supabase JWT RS256 via JWKS), `rate_limit.py` |
| `frontend/src/` | React 18 + TS + Vite. Lazy-loaded pages: Dashboard, **`PortfolioPage.tsx`** (the product center — **6 tabs: Analysis (default) / Holdings / Underwrite / Stress Test / Decisions / Simulation**, in `components/portfolio/`), Profile, SignIn/Auth, Onboarding, Simulate/SimulateReport. **Supabase auth** (`hooks/useAuth.ts`, `pages/SignInPage.tsx`); `utils/api.ts` injects the Bearer token. Vitest + Playwright |
| `scripts/` | DB init, seeds (`seed_properties`, `seed_tokyo`, `seed_kaggle_usa`, `seed_from_csv`, `seed_dev_portfolio`), `backfill_market_signals.py`, `fetch_external_signals.py`, `create_dev_user.py` |
| `doc/` | Architecture & planning docs incl. `market-signal-sources.md`, `SUPABASE_AUTH_SETUP.md`, `investor-portfolio-implementation-plan.md`, `strategy-runtime-plan.md`, `testing-with-csv-dataset.md` |
| `tests/` | ~347 pytest tests (in-memory SQLite, fakeredis, no external services) |

## Portfolio Surface — Analysis & Simulation tabs

`PortfolioPage.tsx` is the product's center of gravity. Two tabs carry the
investor pipeline, both operating on the **selected portfolio's real holdings**:

- **Analysis tab** — renders `PortfolioSummaryReport` from `GET /api/portfolio/{id}/summary`
  (`services/portfolio_summary.build_portfolio_summary`): per-holding cap rate / DSCR /
  CoC / recommendation + the attention list and aggregates.
- **Simulation tab** — free-text strategy run: `POST /api/strategy/extract` → review the
  `StrategyProfile` → `POST /api/strategy/run` → poll `…/status` then `…/result`. Renders
  the per-holding forward projection (`SimulationReport`) and the survival/confidence
  reconciliation (`UnifiedReport`).

**Backend pipeline (reuse, don't duplicate):**
`build_portfolio_summary` → `strategy_runner.project_simulation` →
`unified_report.reconcile_unified_report`, orchestrated by
`strategy_runner.execute_strategy_run`. Every run is audited to `domain_events`
(`strategy.run_started` / `…_completed` / `…_failed`) with the request correlation id,
and emits live step events over Redis pub/sub.

## Database

- **Engine:** PostgreSQL with asyncpg (async SQLAlchemy 2.0)
- **Migrations:** Alembic with async engine (head: `f9a1b2c3d4e5`)
- **Connection:** `postgresql+asyncpg://dev:dev@localhost:5432/realestate`
- **Testing:** In-memory SQLite with JSONB→JSON patching, mocked Redis

## Critical Patterns — Follow These

1. **Event Sourcing:** State-changing flows write to the `domain_events` table with a
   correlation ID, via `services/event_store.py::EventStore.append` (the only writer).
   Strategy runs are audited this way.
2. **Async-first:** All DB, Redis, HTTP, and Claude API calls are async. Use
   `asyncio.Semaphore`/locks for concurrency control.
3. **Provider Pattern:** Market data, maps, and market-signal sources use Protocol-based
   providers (mock + real). Always support both modes.
4. **Resilient external calls:** External HTTP (market data, maps, signal providers) use
   `tenacity` retry with backoff. Inject `httpx.AsyncClient` so tests use `httpx.MockTransport`.
5. **Correlation IDs:** Every request gets a UUID via `middleware/correlation.py`
   (`get_correlation_id()` contextvar). Thread it through logs, events, and decisions.
   Background tasks must capture it at request time (the contextvar does not propagate).
6. **Layered domain runtime is pure:** Code under `domain/` is side-effect free,
   deterministic, no DB / Redis / Claude calls. Projections take inputs, return frozen
   dataclasses. Persistence and orchestration live in `services/` and `api/`.
7. **Lenient projections:** Builders/runtimes in `domain/` log a warning and return a
   sensible default on missing/unknown data — never raise. `ValueError` is reserved for
   actual transitions in the negotiation state-machine primitive.
8. **Market-signal writes go through `services.signal_writer.upsert_signal`** — same
   calendar-day writes for a `(signal_type, subject_type, subject_id)` update in place;
   a different day inserts. Never `db.add(MarketSignal(...))` directly from new code.
9. **Reuse the strategy pipeline:** Build on `portfolio_summary`, `strategy_runner`, and
   `unified_report` rather than re-deriving analysis/simulation/reconciliation logic.

## Configuration

All config via `config.py` (pydantic-settings) reading from `.env`:

| Variable | Default | Notes |
|----------|---------|-------|
| `ANTHROPIC_API_KEY` | (empty) | Claude — listing analysis (`agent/analyst_council`) + portfolio chat import |
| `DATABASE_URL` | `postgresql+asyncpg://dev:dev@localhost:5432/realestate` | |
| `REDIS_URL` | `redis://localhost:6379/0` | Pub/sub for strategy-run step events |
| `MARKET_DATA_PROVIDER` | `mock` | `mock` or real provider |
| `MONTE_CARLO_SCENARIOS` | `300` | Stress-test / financial-model iterations |
| `JURISDICTION` | `us` | `us` or `jp` (Tokyo) |
| `DEFAULT_PREFECTURE_CODE` | `13` | 東京都 (JP mode) |
| `REINFOLIB_MODE` / `REINS_MODE` | `mock` | Legacy fixture-only `services/providers_jp/` mocks — **no consumer reads these** |
| `REINFOLIB_API_KEY` | (empty) | MLIT 不動産情報ライブラリ subscription key — required by the four live `reinfolib_*` signal providers |
| `SUPABASE_URL` | (empty) | Supabase project URL (frontend: `VITE_SUPABASE_URL`) |
| `SUPABASE_SERVICE_ROLE_KEY` | (empty) | Server-only — `scripts/create_dev_user.py` and admin ops |
| `SUPABASE_JWT_ISSUER` | (empty) | Expected `iss`, e.g. `https://<project>.supabase.co/auth/v1` |
| `SUPABASE_JWKS_URL` | (empty) | JWKS endpoint for RS256 key fetch in `middleware/auth.py` |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | Expected `aud` claim |

> Auth middleware is **disabled** (passthrough) when `SUPABASE_JWT_ISSUER`/`SUPABASE_JWKS_URL`
> are empty — useful for tests and bare-DB dev. See `doc/SUPABASE_AUTH_SETUP.md`.
>
> Legacy negotiation-era settings (`MIROFISH_MODE`, `MAX_SIMULATION_ROUNDS`,
> `MAX_BATCH_SCENARIOS`, `MIN_OFFER_PERCENT`, `MAX_COUNTER_ROUNDS`, `MAX_DEAL_VALUE_AUTO`)
> remain in `config.py` but have no consumers after the negotiation removal.

## Layered Domain Runtime

The `domain/` package implements a five-layer pipeline. Every layer is
**pure-Python**, **side-effect free**, **deterministic**, and **lenient**
(missing data → `None` or warning, never raises).

| Layer | Module | Primary Types |
|---|---|---|
| Event taxonomy | `domain/events.py` | `EventNamespace`, `MARKET_EVENTS`, `canonical_event()` |
| Market | `domain/market/` | `MarketContextSnapshot`, `market_event()` |
| Actor / cohort | `domain/actors/` | `ActorSignalState`, `CohortSignalState`, `infer_actor_type()`, `user_profile_signals()`, `cohort_signals()` |
| Reaction | `domain/reactions/` | `ReactionVector`, `ReactionEngine`, `extract_narratives()`, `vector_distance()` |
| Decision | `domain/decisions/` | `DecisionContext`, `DecisionRuntime`, `ListHoldPolicy`, `LeasePolicy`, `ChurnPolicy`, `DevResistancePolicy`, `default_policies()` |
| Outcome | `domain/outcomes/` | `MarketOutcomeSnapshot`, `build_outcome_snapshot()`, `project_*()` |
| Report / replay | `domain/reports/` | report artifacts, `ReplayNarrative`, `replay_reactions()` |

**Persistence boundary:** only `db/models.py::MarketSignal` was added for this runtime.
All other layers are computed read-models — durable state goes through `domain_events`.

**Service-layer bridge:** `services/market_state.py::build_snapshot(db, property_id)` is
the only async entry point that pulls `MarketSignal` rows from PostgreSQL and produces a
`MarketContextSnapshot`. Neighborhood signals are looked up under both `neighborhood_id`
and `zip_code` — property-level signals win, then the first neighborhood key that resolves.

## Market Signal Adoption

The investor underwriting + decision surface reads signals via
`services/market_state.py` and `api/decisions.py`.

| Piece | Path | Purpose |
|---|---|---|
| Backfill (in-DB) | `scripts/backfill_market_signals.py` | Derive `median_sale_price` + `inventory_pressure` per zip and `hazard` per property |
| External fetch CLI | `scripts/fetch_external_signals.py` | `--source <name>` runs one provider, upserts via the shared writer |
| Shared writer | `services/signal_writer.py::upsert_signal` | Idempotent **per calendar day** |
| Provider Protocol | `services/signal_providers/base.py` | `MarketSignalProvider` + frozen `ExternalSignal` DTO |
| Mock provider | `services/signal_providers/mock.py` | Deterministic Chicago zip fixture — no network |
| Chicago Crime | `services/signal_providers/chicago_crime.py` | Real, no API key — SODA `ijzp-q8t2` → `safety_score` |
| HUD FMR | `services/signal_providers/hud_fmr.py` | Fair Market Rent → `median_rent` (API key in `.env`) |
| FRED | `services/signal_providers/fred.py` | Federal Reserve mortgage rate → `loan_rate` |
| FEMA NFHL | `services/signal_providers/fema_nfhl.py` | Flood hazard → `hazard` flags per property |
| Census ACS | `services/signal_providers/census_acs.py` | ACS → `median_rent` + `median_sale_price` per zip |
| REINFOLIB base | `services/signal_providers/reinfolib_base.py` | Shared MLIT client — `Ocp-Apim-Subscription-Key` header + XYZ tile math (lat/lng → tile). 404 = "no data" → `None` |
| REINFOLIB transaction | `services/signal_providers/reinfolib_transaction.py` | MLIT XIT001 取引価格 → `median_sale_price` + `median_unit_price` per municipality |
| REINFOLIB land price | `services/signal_providers/reinfolib_land_price.py` | 地価公示・地価調査 → `land_price_psm` |
| REINFOLIB appraisal | `services/signal_providers/reinfolib_appraisal.py` | 鑑定評価 → `appraised_value_psm` |
| REINFOLIB hazard | `services/signal_providers/reinfolib_hazard.py` | Tile-based hazard → `hazard_flood` / `hazard_landslide` / `hazard_liquefaction` |
| Read API | `GET /api/properties/{id}/market-context` | Wraps `build_snapshot`, returns `MarketContextSnapshot` JSON |

Adding a new provider = ~50 lines: implement the Protocol, register in
`services/signal_providers/registry.py::_FACTORIES`, mock the HTTP call with
`httpx.MockTransport`. See `doc/market-signal-sources.md`.

## Testing Conventions

- All tests in `tests/` using pytest-asyncio
- In-memory SQLite, no external services required
- Mock Redis via fakeredis; no real API/HTTP calls in tests
- Run `pytest tests/ -v` before committing

## Coding Conventions

- Python 3.11+, type hints throughout
- Pydantic v2 for schemas, pydantic-settings for config
- SQLAlchemy 2.0 async style (`select()`, `async_session`)
- structlog for logging (never use `print`)
- FastAPI dependency injection for DB sessions
- UUID primary keys on all models
- JSONB columns for flexible structured data (payloads, snapshots, scenario inputs/outputs)
