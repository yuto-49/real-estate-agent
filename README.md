# Real Estate Agentic System

Full-stack real estate transaction platform with AI agents (Claude API) for buyer/seller/broker negotiation and a MiroFish swarm intelligence layer for market prediction.

## Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (for PostgreSQL and Redis)
- **Node.js 18+** (for the React frontend)
- API keys (optional for dev — mock data is used by default):
  - `ANTHROPIC_API_KEY` — Claude API for agent conversations
  - `TOMTOM_API_KEY` — TomTom Maps for geocoding and neighborhood analysis (free tier, no credit card)

## Quick Start

### 1. Start infrastructure

```bash
cd real-estate-agent

# Start PostgreSQL and Redis in Docker
docker compose up -d db redis

# Verify they're healthy
docker compose ps
```

Expected output: both `db` and `redis` show `healthy` status.

### 2. Install Python dependencies

```bash
pip install -e ".[dev]"
```

This installs FastAPI, SQLAlchemy, Anthropic SDK, structlog, tenacity, geohash2, and all dev/test dependencies.

### 3. Set up the database

```bash
# Run Alembic migrations (creates all tables including domain_events)
alembic upgrade head

# Seed with sample Chicago properties and a dev user
python scripts/seed_properties.py
```

If you haven't run migrations yet (first time), generate the initial migration first:

```bash
alembic revision --autogenerate -m "initial schema with domain_events"
alembic upgrade head
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys (optional — mock data works without them)
```

Key settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/realestate` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `ANTHROPIC_API_KEY` | (empty) | Required for agent conversations |
| `TOMTOM_API_KEY` | (empty) | Geocoding & neighborhood analysis (free: 2,500 req/day) |
| `MARKET_DATA_PROVIDER` | `mock` | `mock` for dev, `zillow` for real data |
| `ENVIRONMENT` | `development` | `development` or `production` |

### 5. Start the API server

```bash
uvicorn main:app --reload
```

The server starts at `http://localhost:8000`. Verify:

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}

curl http://localhost:8000/api/properties/
# Returns seeded Chicago properties
```

### 6. Start the frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173` with API proxy to `:8000`.

### 7. Run tests

```bash
pytest tests/ -v
```

All 70 tests run against an in-memory SQLite database — no Docker required for testing.

## Project Structure

```
real-estate-agent/
├── main.py                    # FastAPI entry point + lifespan
├── config.py                  # Pydantic settings (reads .env)
├── agent/
│   ├── base_agent.py          # Abstract agent with Claude API loop + ACL
│   ├── buyer_agent.py         # Buyer: search, offer, negotiate down
│   ├── seller_agent.py        # Seller: list, evaluate, negotiate up
│   ├── broker_agent.py        # Broker: mediate, contracts, inspections
│   ├── orchestrator.py        # Routes messages to agents, DB-backed context
│   ├── negotiation.py         # State machine + timeout rules
│   ├── negotiation_engine.py  # Multi-turn orchestration, ZOPA detection
│   ├── tool_acl.py            # Role-based tool permissions (frozen map)
│   ├── tool_registry.py       # Tool name → async handler mapping
│   ├── prompts.py             # Versioned system prompts (v2.0.0)
│   ├── guardrails.py          # Hard-coded business rules
│   └── tools/                 # Tool handler implementations
│       ├── search.py          # Property search
│       ├── neighborhood.py    # Maps neighborhood analysis
│       ├── offers.py          # Place/evaluate/accept offers
│       ├── listings.py        # List property, update price
│       ├── comps.py           # Comparable sales
│       └── broker_tools.py    # Mediation, contracts, inspections
├── api/
│   ├── schemas.py             # Pydantic request/response models
│   ├── properties.py          # CRUD: list, get, create, update
│   ├── offers.py              # CRUD with guardrail validation
│   ├── users.py               # User profile CRUD
│   ├── negotiations.py        # Start, offer, accept, event replay
│   ├── reports.py             # Enqueue simulation, status, retrieval
│   ├── webhooks.py            # MiroFish completion callback (HMAC)
│   ├── ws.py                  # WebSocket with ConnectionManager
│   └── ws_events.py           # Typed WS event definitions
├── db/
│   ├── database.py            # Async SQLAlchemy engine + session
│   └── models.py              # All models including DomainEvent
├── services/
│   ├── event_store.py         # Append-only event sourcing
│   ├── geocache.py            # Geohash-keyed Redis cache for Maps
│   ├── redis.py               # Connection pool management
│   ├── pubsub.py              # Redis pub/sub event bus
│   ├── market_data.py         # Thin wrapper → provider
│   ├── market_data_provider.py # Protocol + Mock + Zillow providers
│   ├── maps.py                # TomTom Maps (geocoding + nearby search) with geocache
│   ├── logging.py             # structlog with correlation IDs
│   ├── metrics.py             # In-memory counters/histograms
│   ├── job_queue.py           # Redis Streams job queue
│   ├── simulation_worker.py   # Background simulation processor
│   ├── timeout_checker.py     # Expires stale negotiations
│   └── notifications.py       # WebSocket + email notifications
├── intelligence/
│   ├── seed_assembly.py       # Compiles seed doc from live data
│   ├── mirofish_client.py     # HTTP client with retry + circuit breaker
│   └── report_parser.py       # Transforms MiroFish JSON for display
├── middleware/
│   ├── correlation.py         # X-Correlation-ID header + contextvars
│   ├── auth.py                # JWT auth (HMAC-signed tokens)
│   └── rate_limit.py          # Redis sliding-window rate limiter
├── frontend/                  # React 18 + Vite + TypeScript
│   └── src/
│       ├── pages/             # SearchPage, NegotiationPage, ReportPage
│       ├── components/        # MapView, PropertyCard, NegotiationChat
│       ├── hooks/             # useWebSocket (typed, auto-reconnect)
│       └── utils/             # API client, TypeScript event types
├── tests/                     # 70 tests (pytest-asyncio, in-memory SQLite)
├── alembic/                   # Database migrations (async engine)
├── docker-compose.yml         # Postgres + Redis with healthchecks
├── docker-compose.dev.yml     # Dev: hot reload + debug port
└── docker-compose.prod.yml    # Prod: replicas + resource limits
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Application metrics |
| `GET` | `/api/properties/` | List properties (filters: status, min_price, max_price, property_type) |
| `GET` | `/api/properties/{id}` | Get property details |
| `POST` | `/api/properties/` | Create property listing |
| `PATCH` | `/api/properties/{id}` | Update property |
| `POST` | `/api/offers/` | Create offer (guardrail-validated) |
| `GET` | `/api/offers/{id}` | Get offer |
| `GET` | `/api/offers/` | List offers (filters: property_id, buyer_id) |
| `POST` | `/api/users/` | Create user profile |
| `GET` | `/api/users/{id}` | Get user profile |
| `PATCH` | `/api/users/{id}` | Update user profile |
| `POST` | `/api/negotiations/` | Start negotiation |
| `GET` | `/api/negotiations/{id}` | Get negotiation state + events |
| `POST` | `/api/negotiations/{id}/offer` | Submit offer/counter-offer |
| `POST` | `/api/negotiations/{id}/accept` | Accept and finalize |
| `GET` | `/api/negotiations/{id}/events` | Event replay |
| `POST` | `/api/reports/generate` | Enqueue MiroFish simulation |
| `GET` | `/api/reports/status/{id}` | Check report status |
| `GET` | `/api/reports/{id}` | Get completed report |
| `POST` | `/api/webhooks/mirofish` | MiroFish completion callback |
| `WS` | `/ws/negotiation/{id}` | Real-time negotiation updates |

## Architecture Highlights

### 10 Integrated Enhancements

1. **Event Sourcing** — Append-only `domain_events` table with correlation IDs for full audit trail and replay
2. **Correlation ID Middleware** — Traces requests across services via `X-Correlation-ID` header
3. **Structured Logging** — structlog with auto-injected correlation IDs
4. **Geohash Redis Cache** — Caches TomTom API responses by geohash prefix (24h TTL)
5. **Market Data Provider Pattern** — Protocol-based with Mock (rich Chicago data) and Zillow implementations
6. **Tool ACL** — Frozen permission map enforced before and after Claude API calls
7. **Negotiation Timeouts** — Statutory deadlines per state (48h offers, 10d inspections, 30d closing)
8. **Redis Pub/Sub** — Real-time event distribution across typed channels
9. **MiroFish Retry + Circuit Breaker** — Exponential backoff with jitter, auto-opens after 5 failures
10. **Typed WebSocket Events** — Pydantic models on server, TypeScript enums on client

### Transaction Flow

```
User Message → Orchestrator → Agent (Buyer/Seller/Broker)
                  ↓                      ↓
            DB Context            Claude API (ACL-filtered tools)
                  ↓                      ↓
           Domain Event ←──── Tool Execution (guardrails)
                  ↓
          Redis Pub/Sub → WebSocket → Frontend
```

## Docker Commands

```bash
# Development (hot reload)
docker compose -f docker-compose.dev.yml up

# Production (replicated, resource-limited)
docker compose -f docker-compose.prod.yml up -d

# Just infrastructure (run app locally)
docker compose up -d db redis

# View logs
docker compose logs -f app
```

## Testing

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=term-missing

# Specific test file
pytest tests/test_negotiation_engine.py -v
```

Tests use in-memory SQLite with JSONB→JSON patching, mocked Redis, and no external API calls.

## Architecture Reference

See `REAL_ESTATE_AGENT_ANALYSIS.md` for the full architecture decomposition, metrics framework, risk assessment, and Claude Code build strategy.
