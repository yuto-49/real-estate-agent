# Real Estate Agentic Platform

Tokyo workforce-housing **investor analytics** platform: portfolio underwriting, market-signal intelligence, and forward strategy simulation.

**Stack:** FastAPI + React 18 + TypeScript + Claude API + PostgreSQL 16 + Redis 7

**Domain focus:** Workforce housing -- affordable, accessible housing for essential workers and moderate-income households, with emphasis on regulatory compliance and market-signal-driven intelligence.

> **Scope note (post-pivot).** The buyer/seller negotiation chat, social-sentiment simulator, synthetic market-tick engine, and MiroFish report flow were **removed** (migration `f9a1b2c3d4e5`). `CLAUDE.md` and `architecture.md` are the current source of truth; some sections below have not been fully re-verified.

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
| `ANTHROPIC_API_KEY` | _(empty)_ | Claude — listing analysis + portfolio chat-import extraction |
| `TOMTOM_API_KEY` | _(empty)_ | Maps, geocoding, neighborhood analysis |
| `DATABASE_URL` | `postgresql+asyncpg://dev:dev@localhost:5432/realestate` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `MARKET_DATA_PROVIDER` | `mock` | `mock` for dev, real provider otherwise |
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
pytest tests/test_strategy_events.py -v
```

<img width="1461" height="799" alt="Screenshot 2026-04-01 at 2 38 41 PM" src="https://github.com/user-attachments/assets/9c91cc9d-660b-4241-bc27-921a97db3565" />
<img width="1453" height="780" alt="Screenshot 2026-04-01 at 2 38 55 PM" src="https://github.com/user-attachments/assets/b3497c22-2bbc-4b18-b54e-8c4eed3bc610" />

---

## Project Structure

```
real-estate-agent/
  main.py                     # FastAPI entry point + lifespan, router mounts
  config.py                   # Pydantic settings (reads .env)
  agent/                      # Claude-driven listing analysis
    analyst_council.py        #   Multi-persona listing-analysis council
    analyst_personas.py       #   Persona definitions for the council
  api/                        # FastAPI routers (all mounted in main.py)
    properties.py             #   CRUD + GET /{id}/market-context
    search.py                 #   Property search
    users.py                  #   User profile CRUD
    portfolio.py              #   Portfolios, holdings, /summary, CSV/chat import
    underwrite.py             #   Underwrite, stress-test, listing/parse
    listing_analysis.py       #   Claude listing-analysis council endpoint
    decisions.py              #   GET /holding/{id} — per-holding recommendation
    strategy.py               #   extract / run / status / result / recent
    onboarding.py             #   Onboarding state
    investor_profile.py       #   Investor profile CRUD
    public_config.py          #   Public (frontend) config
    schemas.py                #   All Pydantic request/response models
  db/
    database.py               # Async SQLAlchemy engine + session
    models.py                 # 9 models + 10 enums (investor domain)
  domain/                     # Pure-Python layered runtime (no I/O)
    events / market / actors / reactions / decisions / outcomes / reports
  services/                   # Business logic + I/O
    portfolio_summary.py      #   build_portfolio_summary (/summary aggregator)
    strategy_runner.py        #   execute_strategy_run + pure project_simulation
    unified_report.py         #   reconcile_unified_report (analysis vs simulation)
    strategy_profile.py       #   free-text -> StrategyProfile (heuristic, LLM-pluggable)
    holding_decision.py       #   compute_holding_decision
    market_state.py           #   build_snapshot -> MarketContextSnapshot
    signal_writer.py          #   upsert_signal (idempotent per calendar day)
    event_store.py            #   Append-only domain_events writer
    portfolio_chat_extractor.py  # Claude chat -> holdings
    signal_providers/         #   Pluggable external market-signal providers
    maps.py / redis.py / pubsub.py / metrics.py / market_data*.py
  intelligence/               # Investor analytics
    underwriting.py           #   cap rate / CoC / DSCR / IRR
    depreciation_jp.py        #   JP depreciation schedule
    tax_basic.py / stress_test.py
  middleware/                 # correlation.py, auth.py (Supabase JWT), rate_limit.py
  frontend/                   # React 18 + TypeScript + Vite (Portfolio surface)
  scripts/                    # DB init, seeds, market-signal CLIs, create_dev_user
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
| `GET` | `/api/properties/{id}/market-context` | `MarketContextSnapshot` for a property |
| `GET` | `/api/search/` | Property search |
| `POST` | `/api/users/` · `GET`/`PATCH` `/{id}` | User profile CRUD |
| `GET` | `/api/portfolio/?user_id=` | List a user's portfolios |
| `POST` | `/api/portfolio/` | Create portfolio |
| `GET` | `/api/portfolio/{id}/summary` | `PortfolioSummaryReport` (per-holding analysis) |
| `GET` | `/api/portfolio/{id}/holdings` · `POST`/`DELETE` | Holdings CRUD |
| `POST` | `/api/portfolio/import/csv` · `/import/chat` | CSV / Claude chat import |
| `POST` | `/api/underwrite/` | Underwrite a deal |
| `POST` | `/api/underwrite/stress-test` | Monte Carlo stress test |
| `POST` | `/api/listing/parse` | Parse a free-text listing |
| `POST` | `/api/listings/analyze` | Claude listing-analysis council |
| `GET` | `/api/decisions/holding/{id}` | Per-holding recommendation |
| `POST` | `/api/strategy/extract` | Free text → reviewable `StrategyProfile` |
| `POST` | `/api/strategy/run` | Start a strategy run (analysis → simulation → unified) |
| `GET` | `/api/strategy/{id}/status` · `/result` | Poll / fetch a strategy run |
| `GET` | `/api/onboarding/state` · `/api/investor-profile/*` · `/api/config` | Onboarding, investor profile, public config |

---

## Architecture

```
React frontend --> FastAPI API (api/) --> services/  (portfolio_summary, strategy_runner,
   (Portfolio          |                     holding_decision, market_state, signal_writer)
    surface)           v                       |
              PostgreSQL + Redis               v
                       |          domain/ -- pure projections (no I/O):
                       |          market -> actor -> reaction -> decision -> outcome -> report
                       v
              domain_events (event-sourced audit, correlation id)
              Redis pub/sub (live strategy-run step events)

Claude API: agent/analyst_council (listing analysis) + api/portfolio chat import.
```

### Key Design Patterns

1. **Event Sourcing** -- Append-only `domain_events` table with correlation IDs (via `services/event_store.py`); strategy runs are audited this way
2. **Async-first** -- All DB, Redis, HTTP, and Claude API calls are async
3. **Provider Pattern** -- Market data, maps, and signal sources use Protocol-based providers (mock + real)
4. **Resilient external calls** -- `tenacity` retry/backoff; inject `httpx.AsyncClient` so tests use `httpx.MockTransport`
5. **Pure domain runtime** -- `domain/` is side-effect-free, deterministic, lenient (missing data → default, never raise)
6. **Correlation IDs** -- Every request traced end-to-end; background tasks capture the id at request time
7. **Reuse the strategy pipeline** -- `portfolio_summary` → `strategy_runner.project_simulation` → `unified_report.reconcile_unified_report`

See [architecture.md](architecture.md) and [CLAUDE.md](CLAUDE.md) for the current system design, the layered domain runtime, and the market-signal pipeline.

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
