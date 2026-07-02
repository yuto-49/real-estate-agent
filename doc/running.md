# Running & Verification Guide

## Prerequisites

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 20+ | Frontend build |
| PostgreSQL | 16 | Primary database |
| Redis | 7 | Cache + pub/sub |
| Docker + Compose | latest | Container orchestration (optional) |

---

## 1. Local Development Setup

### 1a. Infrastructure (PostgreSQL + Redis)

**Option A — Docker shared services (recommended):**

```bash
docker compose -f ~/docker-shared-services.yml up -d postgres redis
bash scripts/init-shared-db.sh
```

**Option B — Native installs:**

```bash
# PostgreSQL on localhost:5432, database "realestate", user "dev", password "dev"
createdb -U dev realestate

# Redis on localhost:6379
redis-server --daemonize yes
```

### 1b. Environment Variables

```bash
cp .env.example .env
# Edit .env — at minimum set:
#   DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5432/realestate
#   REDIS_URL=redis://localhost:6379/0
#   ANTHROPIC_API_KEY=sk-...   (required for agent conversations)
```

Auth is **disabled** (passthrough) when `SUPABASE_JWT_ISSUER` and `SUPABASE_JWKS_URL` are empty. Set both to enable JWT verification. See `doc/SUPABASE_AUTH_SETUP.md`.

### 1c. Python Virtual Environment

Create an isolated venv so project dependencies don't conflict with system
packages. Run these commands from the repository root:

```bash
# Create the venv (one time)
python -m venv .venv

# Activate it
# Linux / macOS / Git Bash on Windows:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat

# Verify you're inside the venv
which python        # should print .venv/bin/python  (or .venv\Scripts\python on Windows)
python --version    # 3.11+
```

> **Tip:** Most IDEs (VS Code, PyCharm) auto-detect `.venv/` and activate it
> in their integrated terminals. In VS Code, open the Command Palette →
> *Python: Select Interpreter* → choose the `.venv` entry.

### 1d. Backend

With the venv activated:

```bash
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_properties.py          # seed demo properties
uvicorn main:app --reload                  # http://localhost:8000
```

### 1e. Frontend

```bash
cd frontend
npm install
npm run dev                                # http://localhost:5173
```

### 1f. Dev Auth Account (optional, requires Supabase)

```bash
python scripts/create_dev_user.py
```

---

## 2. Verification Checklist

### 2a. Backend Health

```bash
# Health endpoint
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"0.2.0"}

# Metrics
curl http://localhost:8000/metrics
```

### 2b. Test Suite

```bash
# Full suite (585+ tests, in-memory SQLite, no Docker needed)
pytest tests/ -v

# With coverage report
pytest tests/ --cov=. --cov-report=term-missing

# Coverage target: 80%+
```

### 2c. Test by Layer

```bash
# Domain simulation (pure Python, no I/O — fastest)
pytest tests/test_simulation_models.py \
       tests/test_simulation_shocks.py \
       tests/test_simulation_property_step.py \
       tests/test_simulation_cohort_step.py \
       tests/test_simulation_investor_step.py \
       tests/test_simulation_loop.py -v

# Service orchestration
pytest tests/test_sim_orchestrator.py \
       tests/test_broker_orchestrator.py -v

# Strategy runner (analysis -> simulation -> unified report pipeline)
pytest tests/test_strategy_runner.py \
       tests/test_strategy_runner_steps.py \
       tests/test_strategy_runner_depreciation.py -v

# Market signal providers
pytest tests/test_signal_providers.py -v

# API endpoints
pytest tests/test_api_portfolio.py \
       tests/test_api_underwrite.py \
       tests/test_api_decisions.py -v

# Single test
pytest tests/test_simulation_loop.py::test_simulation_with_rent_decline_shock -v
```

### 2d. Frontend Tests

```bash
cd frontend

# Unit tests (Vitest)
npm run test

# Watch mode
npm run test:watch

# E2E tests (Playwright — requires running backend)
npm run test:e2e
```

### 2e. Type Checking & Linting

```bash
# Python
mypy . --ignore-missing-imports
ruff check .
ruff format --check .

# Frontend
cd frontend && npx tsc --noEmit
```

### 2f. Market Signal Pipeline

```bash
# Backfill signals from existing property data
python scripts/backfill_market_signals.py

# List registered external providers
python scripts/fetch_external_signals.py --list

# Run a specific provider
python scripts/fetch_external_signals.py --source mock
python scripts/fetch_external_signals.py --source chicago_crime
```

### 2g. Simulation Engine Verification

```bash
# Quick smoke test — run a simulation via the API
curl -X POST http://localhost:8000/api/simulation/run \
  -H "Content-Type: application/json" \
  -d '{
    "holding_id": "<your-holding-id>",
    "portfolio_id": "<your-portfolio-id>",
    "max_rounds": 10,
    "shocks": [
      {"round_num": 3, "shock_type": "rent_decline", "magnitude": -0.05, "label": "家賃下落5%"}
    ]
  }'

# Retrieve round-by-round replay
curl http://localhost:8000/api/simulation/<run_id>/replay
```

### 2h. Strategy Run Verification

```bash
# Start a strategy run (requires portfolio + holdings in DB)
curl -X POST http://localhost:8000/api/strategy/run \
  -H "Content-Type: application/json" \
  -d '{"portfolio_id": "<id>", "text": "conservative hold strategy"}'

# Poll status
curl http://localhost:8000/api/strategy/<run_id>
```

---

## 3. Docker Deployment

### 3a. Development (shared network)

```bash
# Requires external postgres + redis on shared-dev network
docker compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

### 3b. Production (self-contained with HTTPS)

```bash
# Set your domain
export DOMAIN=your-domain.com

# Build and launch (includes Caddy + Redis)
docker compose -f docker-compose.deploy.yml up --build -d

# Caddy auto-provisions TLS certificates
# App available at https://your-domain.com
```

### 3c. Production Overrides

```bash
# With production optimizations (gunicorn, nginx)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

---

## 4. Architecture Verification

### 4a. Database Migrations

```bash
# Check current migration state
alembic current

# Apply pending migrations
alembic upgrade head

# Generate a new migration (after model changes)
alembic revision --autogenerate -m "description"
```

### 4b. Key API Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| GET | `/api/properties` | List properties |
| GET | `/api/portfolio` | List portfolios |
| POST | `/api/simulation/run` | Run unified simulation |
| GET | `/api/simulation/{id}/replay` | Get round-by-round replay |
| POST | `/api/strategy/run` | Start strategy analysis |
| GET | `/api/strategy/{id}` | Poll strategy run status |
| GET | `/api/decisions/holding/{id}` | Get holding decision |
| POST | `/api/underwrite` | Run underwriting analysis |

### 4c. Frontend Pages

| Route | Page | Key Feature |
|-------|------|-------------|
| `/` | Dashboard | Overview |
| `/portfolio` | PortfolioPage | 7 tabs: Overview, Holdings, Underwrite, Stress Test, Decisions, Strategy, Simulate |
| `/negotiate` | NegotiationPage | Social simulation workspace |
| `/sign-in` | SignInPage | Supabase authentication |

---

## 5. How It Can Work Better

### 5a. Current Bottlenecks

| Area | Issue | Recommendation |
|------|-------|----------------|
| Simulation store | In-memory `dict` in `api/simulation_unified.py` | Migrate to Redis with TTL expiry for multi-process deployments |
| Strategy runner store | In-memory `dict` in `services/strategy_runner.py` | Same — Redis or PostgreSQL JSONB for durability |
| Broker report store | In-memory `dict` in `services/broker_orchestrator.py` | Same pattern — not durable across restarts |
| Debt service | Hardcoded 600,000 in `domain/simulation/loop.py` | Make configurable via `SimSeed.annual_debt_service` field |
| Convergence | Fixed 2 consecutive stable rounds | Consider configurable stability window |

### 5b. Scaling Recommendations

1. **Background job queue:** Replace in-process simulation execution with Celery or ARQ workers. The simulation loop is CPU-bound and blocks the event loop for large round counts.

2. **Result persistence:** Store `SimResult` in PostgreSQL JSONB or Redis with configurable TTL. Current in-memory stores are lost on restart.

3. **WebSocket streaming:** The `/ws/strategy/{run_id}` endpoint is stubbed. Wire it to `StrategyEventSink.publish_strategy_step()` via Redis pub/sub to stream round-by-round updates to the frontend.

4. **Batch simulation:** Add a `POST /api/simulation/batch` endpoint that runs multiple shock scenarios in parallel and returns comparative results.

5. **Caching:** Cache `build_sim_seed_from_holding()` results with a short TTL — financials rarely change within a session.

### 5c. Reliability Improvements

1. **Input validation:** Add `SimConfig` bounds checking (e.g., `convergence_threshold` must be > 0, shocks must have `round_num <= max_rounds`).

2. **Timeout protection:** Add a wall-clock timeout to `run_simulation()` to prevent runaway loops if convergence never triggers.

3. **Structured logging:** Add structured log entries at simulation start/end/convergence with key metrics for observability.

4. **Error boundaries:** The simulation loop currently propagates all exceptions. Wrap individual round steps in try/except to produce partial results on failure.

5. **Replay persistence:** Write `ReplayFrame` tuples to `domain_events` for audit trail replay. Currently only in-memory.

### 5d. Feature Enhancements

1. **Multi-holding simulation:** Run the unified loop across all holdings in a portfolio simultaneously, modeling cross-holding correlation (e.g., same-zip shocks affect multiple properties).

2. **Monte Carlo overlay:** Layer the existing `intelligence/stress_test.py` Monte Carlo engine on top of the unified simulation — run N scenarios with randomized shock timing/magnitude and return percentile distributions.

3. **Broker PDF export:** Generate a 宅建業法-compliant PDF from `BrokerReport` with disclosure checklist, simulation charts, and audit references.

4. **Shock library:** Persist user-created shock presets in the DB so investors can reuse scenarios across sessions.

5. **Comparison mode:** Run two simulations side-by-side (e.g., "with rent regulation" vs. "without") and highlight divergence points.

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: sqlalchemy` | Dependencies not installed | `pip install -e ".[dev]"` |
| DB connection refused | PostgreSQL not running | Start Docker services or native PostgreSQL |
| `pytest` import error | Custom pytest bootstrap | Run `pytest` from the project root |
| Frontend CORS errors | Backend not running | Start uvicorn on port 8000 |
| Auth 401 errors | Supabase not configured | Leave `SUPABASE_JWT_ISSUER` empty to disable auth |
| Simulation returns SELL immediately | Seed has negative cash flow | Check `HoldingFinancials` — ensure `monthly_rent > monthly_opex` |
| Strategy run status "failed" | Portfolio not found | Verify `portfolio_id` exists in `investor_portfolios` table |
