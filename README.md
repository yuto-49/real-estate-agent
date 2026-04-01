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

This project uses a shared Docker services stack (`~/docker-shared-services.yml`) so multiple projects reuse the same Postgres and Redis.

```bash
# Start shared Postgres and Redis (if not already running)
docker compose -f ~/docker-shared-services.yml up -d postgres redis

# Create the 'realestate' database (first time only)
bash scripts/init-shared-db.sh

# Verify containers are running
docker ps --filter name=dev-postgres --filter name=dev-redis
```

Expected output: `dev-postgres` and `dev-redis` containers are running.

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
| `DATABASE_URL` | `postgresql+asyncpg://dev:dev@localhost:5432/realestate` | PostgreSQL connection |
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
<img width="1461" height="799" alt="Screenshot 2026-04-01 at 2 38 41 PM" src="https://github.com/user-attachments/assets/9c91cc9d-660b-4241-bc27-921a97db3565" />
<img width="1453" height="780" alt="Screenshot 2026-04-01 at 2 38 55 PM" src="https://github.com/user-attachments/assets/b3497c22-2bbc-4b18-b54e-8c4eed3bc610" />


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

# Just infrastructure (run app locally via shared services)
docker compose -f ~/docker-shared-services.yml up -d postgres redis
bash scripts/init-shared-db.sh

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
