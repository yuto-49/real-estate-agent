# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered satei-to-close platform for Tokyo real estate brokerages (不動産仲介向けSaaS). Hedonic valuation (査定), price-vs-probability curves, and negotiation coaching via multi-agent simulation. FastAPI backend + React frontend + Claude API agents.

**Domain focus:** Tokyo real estate brokerage SaaS — AI-assisted satei (price assessment) for listing pitches, asking-price optimization via settlement-probability curves, and negotiation strategy coaching. Targets mid-size and proptech-native Tokyo brokerages. Retains investor portfolio analysis as a secondary surface.

## Quick Commands

```bash
# Full first-time setup
make setup                          # install + db-init + migrate + seed

# Backend
make dev-backend                    # uvicorn --reload on :8000

# Frontend
make dev-frontend                   # vite dev on :5173

# Infrastructure (Postgres + Redis)
make infra                          # docker compose shared services

# Tests
make test                           # backend + frontend
pytest tests/ -v --tb=short         # backend only
pytest tests/test_tier1_features.py -v                                    # single file
pytest tests/test_market_state.py::test_build_snapshot_populates_property_context  # single test
make test-cov                       # backend with coverage report
cd frontend && npm run test -- --run  # frontend unit tests (Vitest)
cd frontend && npm run test:e2e     # Playwright E2E

# Lint & type-check
make check                          # lint + typecheck + test
ruff check .                        # Python lint
ruff format .                       # Python format
cd frontend && npx tsc --noEmit     # TypeScript check

# Database
make db-migrate                     # alembic upgrade head
make db-seed                        # seed properties
make db-seed-tokyo                  # seed Tokyo-specific data
alembic revision --autogenerate -m "description"  # new migration

# Market signals
python scripts/backfill_market_signals.py             # derive from properties table
python scripts/fetch_external_signals.py --list       # registered providers
python scripts/fetch_external_signals.py --source mock # write external signals
```

## Architecture

```
User/Frontend → FastAPI API → Services → Claude Analyst Council (4 personas, parallel)
                    |                         |
              PostgreSQL + Redis        httpx → REINFOLIB / e-Stat / SUUMO
                    |
              Domain Events (append-only)
                    |
              Domain Runtime (pure-Python projections, no I/O)
                    |
              Market → Actors → Reactions → Decisions → Outcomes → Reports
```

The agent layer is an **analyst council** (`agent/analyst_council.py`): 4 personas run in parallel via `asyncio`, each making 1 Claude call (Haiku by default), producing `AnalystVerdict` structs that blend into an overall listing score. Not a chat/negotiation agent.

## Key Directories

| Path | Purpose |
|------|---------|
| `agent/` | Analyst council: `analyst_council.py` (orchestration), `analyst_personas.py` (4 personas with JP prompts) |
| `api/` | 18 FastAPI routers + `schemas.py` + `stubs.py` (501s for removed features) |
| `db/models.py` | 12 SQLAlchemy models + 10 enums (JP-aware: AssetTier, ConstructionType, SeismicCode) |
| `domain/` | Pure-Python layered runtime: events → market → actors → reactions → decisions → outcomes → reports. Plus `domain/simulation/` (cohort/investor/property steps, shocks, loop) |
| `services/` | ~44 modules: business logic, JP data providers, market state, signal writer, satei engine, price probability, strategy runner, portfolio summary |
| `services/providers_jp/` | REINFOLIB, e-Stat, Kokudo Suuchi, REINS providers (mock/live modes) |
| `services/signal_providers/` | Pluggable market-signal Protocol + registry (REINFOLIB transaction/land-price/appraisal/hazard, e-Stat, SUUMO rent, mock) |
| `intelligence/` | Financial models: underwriting (cap rate/CoC/DSCR/IRR), JP depreciation (`money_jp.py` for 法定耐用年数), Monte Carlo stress test, tax |
| `middleware/` | Correlation ID, Supabase JWT (RS256 via JWKS, passthrough when unconfigured), rate limiting |
| `frontend/` | React 18 + TypeScript + Vite + MapLibre GL + Recharts. 13+ pages, Supabase auth, Vitest + Playwright |
| `tests/` | ~54 pytest modules, in-memory SQLite, fakeredis, no external services |
| `scripts/` | DB init/seed, market signal backfill/fetch, dev user creation |
| `doc/` | 28 docs: architecture, tier-1 plan, brokerage pitch, ADRs |

## Database

- **Engine:** PostgreSQL + asyncpg (async SQLAlchemy 2.0)
- **Migrations:** Alembic (15 versions, including pivot migration `f9a1b2c3d4e5` that dropped negotiation/social-sim/market-sim tables)
- **Connection:** `postgresql+asyncpg://dev:dev@localhost:5432/realestate`
- **Testing:** In-memory SQLite with JSONB-to-JSON patching, fakeredis

**Core models:** UserProfile, Property (JP-native columns: address_jp, nearest_stations, built_year, structure, menseki_m2), DomainEvent, MarketSignal, InvestorPortfolio, PortfolioHolding, HoldingFinancials, InvestorProfile, UnderwritingScenario, RentComp, SaleComp, SateiSession

## Critical Patterns

1. **Event Sourcing:** All state changes write to `domain_events` with correlation ID.
2. **Async-first:** All DB, Redis, HTTP, Claude API calls must be async.
3. **Domain purity:** `domain/` is side-effect free, deterministic, no I/O. Persistence lives in `services/` and `api/`.
4. **Lenient projections:** Domain builders log warnings and return defaults on missing data — never raise (except `ValueError` for invalid state transitions).
5. **Signal writer:** Market-signal writes go through `services.signal_writer.upsert_signal` — idempotent per calendar day. Never `db.add(MarketSignal(...))` directly.
6. **Provider pattern:** Market data and maps use Protocol-based providers with mock + real modes. External providers must inject `httpx.AsyncClient` so tests use `httpx.MockTransport`.
7. **Correlation IDs:** Every request gets a UUID via middleware, threaded through logs/events.
8. **JP jurisdiction:** `config.jurisdiction` defaults to `jp_tokyo`. Currency is JPY, depreciation uses 法定耐用年数 by construction type, areas in m2.

## Configuration

All config via `config.py` (pydantic-settings) from `.env`. Key variables:

| Variable | Default | Notes |
|----------|---------|-------|
| `ANTHROPIC_API_KEY` | (empty) | Required for analyst council |
| `DATABASE_URL` | `postgresql+asyncpg://dev:dev@localhost:5432/realestate` | |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `JURISDICTION` | `jp_tokyo` | Enforces JP formatters and guardrails |
| `REINS_MODE` / `REINFOLIB_MODE` | `mock` | `mock` or `live` for JP data providers |
| `EMBEDDER_MODE` | `hash` | `hash` (deterministic), `local_st`, `voyage` |
| `MONTE_CARLO_SCENARIOS` | `300` | Financial model iterations |
| `SUPABASE_URL` | (empty) | Also exposed as `VITE_SUPABASE_URL` |
| `SUPABASE_JWT_ISSUER` / `SUPABASE_JWKS_URL` | (empty) | Auth disabled (passthrough) when empty |

## Tier 1 Features (Current Roadmap)

| Feature | Key Files | Purpose |
|---|---|---|
| **Satei Comp Grid** (査定コンプグリッド) | `services/satei_engine.py`, `api/satei.py`, `frontend/src/pages/SateiPage.tsx` | Comparable-based valuation with hedonic adjustment grid, pulls REINFOLIB transactions |
| **Price-vs-Probability Curve** (価格帯別成約確率カーブ) | `services/price_probability.py`, `api/price_probability.py` | "List at X yen -> Y% close probability within 30/60/90/180 days" |
| **Negotiation Coach** (交渉戦略コーチ) | `services/negotiation_coach.py`, `api/negotiation_coach.py`, `frontend/src/pages/NegotiationCoachPage.tsx` | Broker rehearsal tool: counterparty simulation, ZOPA analysis, concession ladders |

See `doc/TIER1_IMPLEMENTATION_PLAN.md` for full specs and `doc/BROKERAGE_PITCH.md` for go-to-market.

## Stubbed / Removed Features

Migration `f9a1b2c3d4e5` dropped negotiation chat, social simulation, and market-tick tables. These APIs return 501 via `api/stubs.py`: negotiations, reports, social-sim, visualization, agent. WebSocket routes are stub-only.

## Coding Conventions

- Python 3.11+, type hints, Pydantic v2
- SQLAlchemy 2.0 async style (`select()`, `async_session`)
- structlog for logging (never `print`)
- UUID primary keys, JSONB for flexible structured data
- Ruff for lint/format (line length 100, rules: E/F/I/N/W/UP)
- Frontend: React 18, TypeScript 5.6, Vite 8, MapLibre GL
