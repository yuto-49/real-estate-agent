# CLAUDE.md — Real Estate Agentic Platform

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
pytest tests/ -v                   # 70 tests, in-memory SQLite, no Docker needed
pytest tests/ --cov=. --cov-report=term-missing
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

Social Simulation (upcoming):
  Synthetic Households → Social Graph → Opinion Rounds → Narrative Clusters → MiroFish Report → Negotiation
```

## Key Directories

| Path | Purpose |
|------|---------|
| `agent/` | Multi-agent system: base agent, buyer/seller/broker/assistant, orchestrator, negotiation engine, tool ACL, prompts v2.0.0 |
| `agent/tools/` | Tool handlers: search, neighborhood, offers, listings, comps, counter, broker, intelligence |
| `api/` | FastAPI routers: properties, offers, users, negotiations, reports, simulation, batch, webhooks, ws |
| `api/schemas.py` | All Pydantic request/response models |
| `db/models.py` | 13 SQLAlchemy models (UserProfile, Property, Offer, Negotiation, AgentDecision, AgentMemory, MiroFishReport, MiroFishSeed, SimulationResult, DomainEvent) |
| `services/` | Business logic: event store, negotiation simulator, batch simulator, persona generator, scenario variants, maps, market data, Redis, pub/sub, metrics, job queue |
| `intelligence/` | MiroFish pipeline: seed assembly, HTTP client (circuit breaker + retry), financial models (Monte Carlo, cash flow, tax), report parser |
| `middleware/` | Correlation ID, JWT auth, rate limiting |
| `frontend/src/` | React 18 + TypeScript + Vite: 5 pages, 18 components, typed WebSocket |
| `scripts/` | DB init, seed (properties, CSV, Kaggle), test helpers |
| `doc/` | Architecture docs, testing guide, business AI skeleton |

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

## Configuration

All config via `config.py` (pydantic-settings) reading from `.env`:

| Variable | Default | Notes |
|----------|---------|-------|
| `ANTHROPIC_API_KEY` | (empty) | Required for agent conversations |
| `DATABASE_URL` | `postgresql+asyncpg://dev:dev@localhost:5432/realestate` | |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `MIROFISH_MODE` | `mock` | `mock` or `live` |
| `MARKET_DATA_PROVIDER` | `mock` | `mock` or `zillow` |
| `MAX_SIMULATION_ROUNDS` | `30` | Negotiation simulation cap |
| `MAX_BATCH_SCENARIOS` | `6` | Batch simulation limit |
| `MONTE_CARLO_SCENARIOS` | `300` | Financial model iterations |

## Social Simulation (In Progress)

See `SOCIAL_SIMULATION_IMPLEMENTATION.md` for full plan. Key additions:

- **HouseholdProfile** model with opinion fields (sentiment, policy support, satisfaction, influence, communication style)
- **HouseholdSocialEdge** model for social graph (neighbor, income peer, language peer, demographic edges)
- **SocialSimulationRun** + **SocialSimulationAction** models for tracking simulation state
- **SocialSimulator** engine: opinion rounds with Claude API, convergence detection, narrative clustering
- **Social Report Bridge:** translates simulation output → MiroFishReport format for seamless integration with existing negotiation pipeline
- **API:** `POST /api/social-sim/start`, `GET .../status`, `GET .../result`, `POST .../generate-report`

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
