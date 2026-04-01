# Real Estate Agentic Platform

Multi-agent real estate negotiation platform with social behavior simulation, intelligence pipeline, and workforce housing analysis.

**Stack:** FastAPI + React 18 + TypeScript + Claude API + PostgreSQL 16 + Redis 7

**Domain focus:** Workforce housing -- affordable, accessible housing for essential workers and moderate-income households, with emphasis on regulatory compliance and community-driven intelligence.

---

## Prerequisites

### macOS

| Tool | Install |
|------|---------|
| **Homebrew** | `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` |
| **Python 3.11+** | `brew install python@3.11` |
| **Node.js 18+** | `brew install node` |
| **Docker Desktop** | `brew install --cask docker` (then open Docker Desktop from Applications) |
| **Git** | Pre-installed, or `xcode-select --install` |

### Windows

| Tool | Install |
|------|---------|
| **Python 3.11+** | Download from [python.org](https://www.python.org/downloads/) -- check **"Add Python to PATH"** during install |
| **Node.js 18+** | Download LTS from [nodejs.org](https://nodejs.org/) |
| **Docker Desktop** | Download from [docker.com](https://www.docker.com/products/docker-desktop/) -- enable **WSL 2 backend**, restart after install |
| **Git** | Download from [git-scm.com](https://git-scm.com/download/win) |

> **Windows terminal:** Use **Git Bash** or **WSL 2** (recommended). All commands below use bash syntax. On PowerShell, replace `~` with `$HOME` and adjust path separators as needed.

**Optional API keys** (mock data works without them):
- `ANTHROPIC_API_KEY` -- Claude API for agent conversations
- `TOMTOM_API_KEY` -- TomTom Maps for geocoding and neighborhood analysis (free tier, 2,500 req/day)

---

## Quick Start

### 1. Clone and enter the repository

```bash
git clone <repository-url>
cd real-estate-agent
```

### 2. Start infrastructure (PostgreSQL + Redis)

The project uses a shared Docker services file for database and cache:

```bash
docker compose -f ~/docker-shared-services.yml up -d postgres redis
```

<details>
<summary><strong>Alternative: standalone Docker setup (no shared services file)</strong></summary>

**macOS / Linux / Git Bash:**
```bash
docker run -d --name dev-postgres \
  -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev \
  -p 5432:5432 postgres:16-alpine

docker run -d --name dev-redis \
  -p 6379:6379 redis:7-alpine
```

**Windows (PowerShell):**
```powershell
docker run -d --name dev-postgres `
  -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev `
  -p 5432:5432 postgres:16-alpine

docker run -d --name dev-redis `
  -p 6379:6379 redis:7-alpine
```

</details>

Verify containers are running:

```bash
docker ps --filter name=dev-postgres --filter name=dev-redis
```

### 3. Initialize the database

**macOS / Linux / Git Bash:**
```bash
bash scripts/init-shared-db.sh
```

**Windows (PowerShell / CMD):**
```powershell
docker exec dev-postgres psql -U dev -c "CREATE DATABASE realestate;"
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your API keys. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | _(empty)_ | Required for agent conversations |
| `TOMTOM_API_KEY` | _(empty)_ | Maps, geocoding, neighborhood analysis |
| `DATABASE_URL` | `postgresql+asyncpg://dev:dev@localhost:5432/realestate` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `MARKET_DATA_PROVIDER` | `mock` | `mock` for dev, `zillow` for real data |
| `MIROFISH_MODE` | `mock` | `mock` or `live` |
| `ENVIRONMENT` | `development` | `development` or `production` |

See [Configuration](#configuration) for the full list.

### 5. Set up the backend

**macOS / Linux / Git Bash:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_properties.py
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
python scripts\seed_properties.py
```

**Windows (CMD):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -e ".[dev]"
alembic upgrade head
python scripts\seed_properties.py
```

### 6. Start the backend

```bash
uvicorn main:app --reload
```

The API runs at **http://localhost:8000**.
- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 7. Start the frontend

Open a **new terminal**, then:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at **http://localhost:5173** with API proxy to `:8000`.

---

## Running Tests

Tests use in-memory SQLite and mocked Redis -- no Docker or external services needed.

```bash
# All tests
pytest tests/ -v

# With coverage report
pytest tests/ --cov=. --cov-report=term-missing

# Specific test file
pytest tests/test_negotiation_engine.py -v
```

<img width="1461" height="799" alt="Screenshot 2026-04-01 at 2 38 41 PM" src="https://github.com/user-attachments/assets/9c91cc9d-660b-4241-bc27-921a97db3565" />
<img width="1453" height="780" alt="Screenshot 2026-04-01 at 2 38 55 PM" src="https://github.com/user-attachments/assets/b3497c22-2bbc-4b18-b54e-8c4eed3bc610" />

---

## Project Structure

```
real-estate-agent/
  main.py                     # FastAPI entry point + lifespan
  config.py                   # Pydantic settings (reads .env)
  agent/                      # Multi-agent system
    base_agent.py             #   Abstract agent with Claude API loop + ACL
    buyer_agent.py            #   Buyer: search, offer, negotiate down
    seller_agent.py           #   Seller: list, evaluate, negotiate up
    broker_agent.py           #   Broker: mediate, contracts, inspections
    orchestrator.py           #   Routes messages to agents, DB-backed context
    negotiation.py            #   State machine + timeout rules
    negotiation_engine.py     #   Multi-turn orchestration, ZOPA detection
    tool_acl.py               #   Role-based tool permissions (frozen map)
    guardrails.py             #   Hard-coded business rules
    prompts.py                #   Versioned system prompts (v2.0.0)
    tools/                    #   Tool handler implementations
  api/                        # FastAPI routers
    properties.py             #   CRUD: list, get, create, update
    offers.py                 #   CRUD with guardrail validation
    users.py                  #   User profile CRUD
    negotiations.py           #   Start, offer, accept, event replay
    reports.py                #   Enqueue simulation, status, retrieval
    households.py             #   Household profile management
    social_simulation.py      #   Social simulation endpoints
    schemas.py                #   All Pydantic request/response models
    webhooks.py               #   MiroFish completion callback (HMAC)
    ws.py                     #   WebSocket with ConnectionManager
  db/
    database.py               # Async SQLAlchemy engine + session
    models.py                 # All SQLAlchemy models
  services/                   # Business logic
    event_store.py            #   Append-only event sourcing
    negotiation_simulator.py  #   Core negotiation simulation engine
    batch_simulator.py        #   Parallel scenario runner
    persona_generator.py      #   Synthetic buyer/seller profiles
    social_simulator.py       #   Social behavior simulation engine
    social_report_bridge.py   #   Social output -> MiroFish report format
    market_data_provider.py   #   Protocol + Mock + Zillow providers
    maps.py                   #   TomTom Maps with geocache
    redis.py                  #   Connection pool management
    pubsub.py                 #   Redis pub/sub event bus
  intelligence/               # MiroFish pipeline
    seed_assembly.py          #   Compiles seed doc from live data
    mirofish_client.py        #   HTTP client with retry + circuit breaker
    report_parser.py          #   Transforms MiroFish JSON for display
    financial_models.py       #   Monte Carlo, DCF, tax models
  middleware/                 # Request middleware
    correlation.py            #   X-Correlation-ID header
    auth.py                   #   JWT auth (HMAC-signed)
    rate_limit.py             #   Redis sliding-window rate limiter
  frontend/                   # React 18 + TypeScript + Vite
  scripts/                    # Database init, seed data, test helpers
  alembic/                    # Database migration versions
  tests/                      # pytest-asyncio test suite
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Application metrics |
| `GET` | `/api/properties/` | List properties (filters: status, min/max price, type) |
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
| `POST` | `/api/social-sim/start` | Start social behavior simulation |
| `GET` | `/api/social-sim/status/{id}` | Check simulation status |
| `GET` | `/api/social-sim/result/{id}` | Get simulation result |
| `POST` | `/api/social-sim/generate-report` | Generate MiroFish report from simulation |

---

## Architecture

```
User/Frontend --> FastAPI API --> Orchestrator --> Claude Agents (buyer/seller/broker/assistant)
                      |                                |
                PostgreSQL + Redis           Tool Execution (ACL-enforced)
                      |                                |
                Domain Events <------------- Guardrails + Business Rules
                      |
               Redis Pub/Sub --> WebSocket --> React Frontend

Social Simulation:
  Synthetic Households --> Social Graph --> Opinion Rounds --> Narrative Clusters --> MiroFish Report --> Negotiation
```

### Key Design Patterns

1. **Event Sourcing** -- Append-only `domain_events` table with correlation IDs for full audit trail and replay
2. **Tool ACL** -- Frozen permission map enforced before and after Claude API calls
3. **Guardrails** -- Hard-coded business rules (offers >= 50% asking, max auto-approved $2M)
4. **Async-first** -- All DB, Redis, HTTP, and Claude API calls are async
5. **Provider Pattern** -- Market data and maps use Protocol-based providers (mock + real)
6. **Circuit Breaker** -- External service calls use tenacity retry + circuit breaker (3 retries, exponential backoff)
7. **Correlation IDs** -- Every request traced end-to-end via UUID correlation IDs

### Negotiation State Machine

```
IDLE -> OFFER_PENDING -> COUNTER_PENDING -> ... -> ACCEPTED -> CONTRACT_PHASE -> INSPECTION -> CLOSING -> CLOSED
                                                             /
                                          REJECTED / WITHDRAWN / ESCALATED
```

- Round 5+: ZOPA detection (spread <= 3% suggests midpoint)
- Round 5+ with spread > 10%: auto-broker mediation
- Round 10+: auto-escalation
- Deadlines: 48h offers, 72h contracts, 10d inspection, 30d closing

See [architecture.md](architecture.md) for the full system design, workforce housing model, legal/compliance audit trail, and simulation engine details.

---

## Configuration

All config via `config.py` (pydantic-settings) reading from `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | _(empty)_ | Required for agent conversations |
| `DATABASE_URL` | `postgresql+asyncpg://dev:dev@localhost:5432/realestate` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `TOMTOM_API_KEY` | _(empty)_ | Maps and geocoding |
| `MIROFISH_MODE` | `mock` | `mock` or `live` |
| `MIROFISH_API_URL` | `http://localhost:5001` | MiroFish service endpoint |
| `MARKET_DATA_PROVIDER` | `mock` | `mock` or `zillow` |
| `MAX_SIMULATION_ROUNDS` | `30` | Negotiation simulation cap |
| `MAX_BATCH_SCENARIOS` | `6` | Batch simulation limit |
| `MONTE_CARLO_SCENARIOS` | `300` | Financial model iterations |
| `MAX_DEAL_VALUE_AUTO` | `2000000` | Max auto-approved deal value |
| `MIN_OFFER_PERCENT` | `0.50` | Minimum offer as fraction of asking price |
| `MAX_COUNTER_ROUNDS` | `10` | Max negotiation counter rounds |

---

## Docker

### Development (hot reload + debug port)

```bash
docker compose -f docker-compose.dev.yml up --build
```

### Production (replicated, resource-limited)

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

### Infrastructure only (run app locally)

```bash
docker compose -f ~/docker-shared-services.yml up -d postgres redis
bash scripts/init-shared-db.sh
```

> These compose files expect the `shared-dev` Docker network. Create it if it doesn't exist:
> ```bash
> docker network create shared-dev
> ```

---

## Seed Data

```bash
# Default sample Chicago properties + dev user
python scripts/seed_properties.py

# Chicago 2024 Kaggle dataset
python scripts/seed_kaggle_chicago_2024.py

# Household profiles (for social simulation)
python scripts/seed_households.py

# Properties from CSV file
python scripts/seed_from_csv.py
```

---

## Troubleshooting

### macOS

| Issue | Fix |
|-------|-----|
| `asyncpg` build fails | `brew install libpq` and ensure it's on PATH |
| Docker commands fail | Open Docker Desktop and verify the engine is running |
| Port 5432 in use | `lsof -i :5432` to find the process, or change port in `.env` |
| Port 8000 in use | `lsof -i :8000` to find the process |
| `python3` not found | `brew install python@3.11` and restart terminal |
| `npm` not found | `brew install node` and restart terminal |

### Windows

| Issue | Fix |
|-------|-----|
| `pip` / `python` not recognized | Re-install Python with **"Add to PATH"** checked |
| Docker fails to start | Enable WSL 2 and hardware virtualization (VT-x/AMD-V) in BIOS |
| `bash` not found | Use Git Bash or WSL 2 instead of CMD/PowerShell for bash scripts |
| `alembic` / `uvicorn` not found | Ensure virtual environment is activated (`.venv\Scripts\activate`) |
| Port conflicts | `netstat -ano | findstr :5432` to find blocking processes |
| Line ending issues | Run `git config core.autocrlf true` before cloning |
| `asyncpg` install fails | Install [Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) |
