# Backend Architecture

Complete guide to how the FastAPI backend works in this application.

## Table of Contents

- [Application Lifecycle](#application-lifecycle)
- [Request Flow](#request-flow)
- [Configuration](#configuration)
- [Database Layer](#database-layer)
- [API Routers](#api-routers)
- [Service Layer](#service-layer)
- [Domain Layer](#domain-layer)
- [Agent Layer (Analyst Council)](#agent-layer-analyst-council)
- [Intelligence Layer](#intelligence-layer)
- [Middleware](#middleware)
- [Data Providers (JP)](#data-providers-jp)
- [Market Signal Pipeline](#market-signal-pipeline)
- [End-to-End Request Examples](#end-to-end-request-examples)
- [Testing](#testing)

---

## Application Lifecycle

**Entry point:** `main.py`

The FastAPI app uses a lifespan context manager for startup/shutdown:

```
Startup:
  1. setup_logging(settings.log_level)  — structlog configuration
  2. Yield to request handling

Shutdown:
  1. Close maps_service (TomTom HTTP client)
  2. Dispose SQLAlchemy engine (connection pool)
  3. Close Redis connection
```

**Middleware stack** (applied in order):
1. `CorrelationIdMiddleware` — assigns/extracts `X-Correlation-ID` per request
2. `CORSMiddleware` — configured from `settings.cors_allowed_origins_list`

**Health & observability:**
- `GET /health` — liveness check
- `GET /metrics` — Prometheus-style export via `services/metrics.py`

---

## Request Flow

Every HTTP request follows this path:

```
HTTP Request
  │
  ├─ CorrelationIdMiddleware  → assigns UUID, stores in contextvars
  ├─ CORSMiddleware           → origin validation
  │
  ▼
FastAPI Router
  │
  ├─ Pydantic schema validation (api/schemas.py)
  ├─ Dependency injection: get_db() → AsyncSession
  │
  ▼
Service Layer (services/)
  │
  ├─ Business logic, orchestration
  ├─ Database queries via SQLAlchemy async
  ├─ External API calls via httpx.AsyncClient
  │
  ▼
Domain Layer (domain/)    ←── pure-Python, no I/O
  │
  ├─ Frozen dataclasses, projections
  ├─ Policy evaluation, reaction vectors
  │
  ▼
Response serialization → JSON
```

---

## Configuration

**File:** `config.py` — Pydantic `BaseSettings` reading from `.env`

Key configuration groups:

| Group | Variables | Purpose |
|-------|-----------|---------|
| **Database** | `DATABASE_URL` | PostgreSQL async connection (`postgresql+asyncpg://`) |
| **Cache** | `REDIS_URL` | Redis for pub/sub and caching |
| **Auth** | `SUPABASE_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWKS_URL` | JWT validation; auth disabled when empty |
| **AI** | `ANTHROPIC_API_KEY` | Claude API for analyst council and chat extraction |
| **JP Providers** | `REINS_MODE`, `REINFOLIB_MODE` | `mock` or `live` for data providers |
| **Jurisdiction** | `JURISDICTION` | `jp_tokyo` (default) — enforces JPY, m², 法定耐用年数 |
| **Embeddings** | `EMBEDDER_MODE` | `hash` (deterministic), `local_st`, `voyage` |
| **Simulation** | `MONTE_CARLO_SCENARIOS` | Default 300 iterations for stress tests |
| **Frontend** | `PUBLIC_API_BASE_URL`, `PUBLIC_WS_BASE_URL`, `PUBLIC_MAP_STYLE_URL` | Exposed via `GET /api/config` |

The `public_runtime_config()` method returns a dict consumed by the frontend at startup.

---

## Database Layer

**Files:** `db/database.py`, `db/models.py`

**Engine:** AsyncEngine with `asyncpg` driver, session via `async_sessionmaker`.

**Dependency injection:**
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
```

### Models (12 tables)

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│   UserProfile   │────▶│ InvestorPortfolio │────▶│ PortfolioHolding  │
│                 │     │                  │     │                   │
│ supabase_user_id│     │ investment_      │     │ property_id (FK)  │──▶ Property
│ preferred_mode  │     │ strategy         │     │ asset_class       │
│ budget_min/max  │     │                  │     │ status            │
└─────────────────┘     └──────────────────┘     └───────────────────┘
        │                                               │
        ▼                                               ▼
┌─────────────────┐                           ┌───────────────────┐
│ InvestorProfile │                           │ HoldingFinancials │
│                 │                           │                   │
│ strategy        │                           │ cost_basis        │
│ target_cap_rate │                           │ current_value     │
│ geography(JSON) │                           │ loan_balance      │
└─────────────────┘                           │ monthly_rent      │
                                              │ vacancy_rate      │
                                              └───────────────────┘

┌─────────────────┐     ┌──────────────────┐
│    Property     │     │   MarketSignal   │
│                 │     │                  │
│ address_jp      │     │ signal_type      │
│ menseki_m2      │     │ subject_type     │  (property | neighborhood | jurisdiction)
│ built_year      │     │ subject_id       │
│ construction_   │     │ value (Float)    │
│   type          │     │ observed_at      │
│ asset_tier      │     │ source           │
│ seismic_code    │     └──────────────────┘
└─────────────────┘
        │
        ├──▶ SateiSession (valuation results + adjustment_grid JSONB)
        ├──▶ RentComp (SUUMO/HOMES rent comparables)
        ├──▶ SaleComp (REINFOLIB transaction comparables)
        └──▶ UnderwritingScenario (inputs/outputs JSONB)

┌─────────────────┐
│  DomainEvent    │  ← append-only event sourcing
│                 │
│ correlation_id  │
│ event_type      │
│ aggregate_type  │
│ aggregate_id    │
│ payload (JSONB) │
│ sequence        │
└─────────────────┘
```

**JP-specific enums:** `AssetTier` (one_room, aparuto, family_mansion), `ConstructionType` (wood/light_steel/steel/rc/src with statutory useful life), `SeismicCode` (kyu_taishin pre-1981, shin_taishin post-1981).

**Testing:** In-memory SQLite with JSONB→JSON column patching. fakeredis for Redis. No external services needed.

---

## API Routers

All routers live in `api/` and are mounted in `main.py` under `/api/`.

### Tier 1 — Core Brokerage Features

#### Satei (査定 Valuation) — `api/satei.py`

| Endpoint | Purpose |
|----------|---------|
| `POST /api/satei/compute` | Compute valuation from comps with hedonic adjustments |
| `GET /api/satei/user/{user_id}` | List user's past satei sessions |
| `GET /api/satei/{session_id}` | Retrieve a specific session |
| `PATCH /api/satei/{session_id}/adjustments` | Override comp adjustments, recompute |

Flow: Query `SaleComp` rows by area → filter by similarity (±30% m², ±5min walk) → apply hedonic adjustments (age, area, walk distance, construction premium) → weighted average → confidence band.

#### Price-vs-Probability — `api/price_probability.py`

| Endpoint | Purpose |
|----------|---------|
| `POST /api/price-probability/compute` | Monte Carlo: "list at X yen → Y% close within N days" |

Runs `MONTE_CARLO_SCENARIOS` iterations with perturbed market assumptions to produce probability curves at 30/60/90/180 day horizons.

#### Negotiation Coach (交渉戦略コーチ) — `api/negotiation_coach.py`

| Endpoint | Purpose |
|----------|---------|
| `POST /api/negotiation-coach/start` | Start a coaching session |
| `GET /api/negotiation-coach/{session_id}` | Get session state |

Broker rehearsal tool — simulates counterparty responses, ZOPA analysis, concession ladders.

### Portfolio & Investment Surface

#### Portfolio CRUD — `api/portfolio.py`

| Endpoint | Purpose |
|----------|---------|
| `POST /api/portfolio/` | Create portfolio |
| `GET /api/portfolio/?user_id=X` | List user's portfolios |
| `GET /api/portfolio/{id}` | Get single portfolio |
| `DELETE /api/portfolio/{id}` | Delete with cascade |
| `POST /api/portfolio/{id}/holdings` | Add holding |
| `GET /api/portfolio/{id}/holdings` | List holdings |
| `DELETE /api/portfolio/{id}/holdings/{hid}` | Remove holding |
| `POST /api/portfolio/import/csv` | Bulk import from CSV |
| `POST /api/portfolio/import/chat` | Extract holdings from chat via Claude |
| `POST /api/portfolio/import/chat/confirm` | Confirm chat-extracted holdings |
| `POST /api/portfolio/from-property` | Create portfolio from a single property |
| `GET /api/portfolio/{id}/aggregate` | Cross-holding financial aggregates |
| `GET /api/portfolio/{id}/summary` | Full summary with decision recommendations |

Bulk import is idempotent: keyed on `(user_id, address)`. Existing holdings get financials updated; new ones are inserted. Entire operation is transactional.

#### Underwriting — `api/underwrite.py`

| Endpoint | Purpose |
|----------|---------|
| `POST /api/underwrite` | Compute cap rate, CoC, DSCR, IRR |
| `POST /api/underwrite/stress-test` | Monte Carlo stress test (300–5000 iterations) |
| `POST /api/listing/parse` | Parse listing URL → structured data |

#### Decisions — `api/decisions.py`

| Endpoint | Purpose |
|----------|---------|
| `GET /api/decisions/holding/{id}` | Recommendation for a single holding (HOLD/SELL/RAISE_RENT/REFI/IMPROVE) |

#### Strategy — `api/strategy.py`

| Endpoint | Purpose |
|----------|---------|
| `POST /api/strategy/extract` | Free text → `StrategyProfile` via Claude |
| `POST /api/strategy/run` | Start async strategy run (returns 202) |
| `GET /api/strategy/status/{run_id}` | Poll for completion |
| `GET /api/strategy/recent?user_id=X` | Recent runs |

### Other Routers

| Router | File | Key Endpoints |
|--------|------|---------------|
| Properties | `api/properties.py` | CRUD, recommend, market-context |
| Search | `api/search.py` | Filtered property search |
| Users | `api/users.py` | Profile management |
| Listing Analysis | `api/listing_analysis.py` | Analyst council review (`POST /api/listings/{id}/analyze`) |
| Rent Comps | `api/rent_comps.py` | Rent comparable validation |
| Signals | `api/signals.py` | Market signal read API |
| Simulation | `api/simulation_unified.py` | Unified simulation orchestration |
| Onboarding | `api/onboarding.py` | Investor onboarding wizard |
| Config | `api/public_config.py` | Frontend runtime config |

### Stubbed Routes — `api/stubs.py`

These features were removed in the pivot (migration `f9a1b2c3d4e5`) and return **501 Not Implemented**:

- `/api/negotiations/*` — negotiation chat
- `/api/reports/*` — report generation
- `/api/social-sim/*` — social simulation
- `/api/visualization/*` — visualization
- `/api/agent/*` — agent chat
- WebSocket routes: `/ws/negotiations/{id}`, `/ws/strategy/{id}`

---

## Service Layer

Business logic lives in `services/`. Services are called by API routers and orchestrate database queries, domain projections, and external API calls.

### Core Services

| Service | File | Purpose |
|---------|------|---------|
| **Satei Engine** | `services/satei_engine.py` | Hedonic valuation: query comps → filter by similarity → apply adjustments → weighted average |
| **Price Probability** | `services/price_probability.py` | Monte Carlo simulation for close probability curves |
| **Market State** | `services/market_state.py` | `build_snapshot(db, property_id)` — pulls MarketSignal rows, returns frozen `MarketContextSnapshot` |
| **Signal Writer** | `services/signal_writer.py` | `upsert_signal()` — idempotent per calendar day. All market signal writes go through this |
| **Event Store** | `services/event_store.py` | Append-only event sourcing: `append()`, `get_events()`, `replay_aggregate()` |
| **Holding Decision** | `services/holding_decision.py` | Orchestrates market snapshot + reaction vector + policy evaluation → recommendation |
| **Portfolio Summary** | `services/portfolio_summary.py` | Aggregates all holdings: metrics, decisions, attention items, market coverage |
| **Strategy Runner** | `services/strategy_runner.py` | Async strategy execution: extract profile → build summary → simulate → unify |
| **Strategy Profile** | `services/strategy_profile.py` | Free-text → `StrategyProfile` via Claude (LLM-pluggable, heuristic fallback) |
| **Property Recommender** | `services/property_recommender.py` | Rank properties against investor profile |
| **Broker Orchestrator** | `services/broker_orchestrator.py` | Broker workflow orchestration |
| **Rent Validator** | `services/rent_validator.py` | Rent comp validation and filtering |
| **Sim Orchestrator** | `services/sim_orchestrator.py` | Simulation job orchestration |
| **Unified Report** | `services/unified_report.py` | Analysis vs simulation reconciliation |

### JP-Specific Services

| Service | File | Purpose |
|---------|------|---------|
| **Money JP** | `services/money_jp.py` | JPY formatting, statutory depreciation (法定耐用年数) lookup by construction type |
| **Address JP** | `services/address_jp.py` | Japanese address parsing and formatting |
| **Maps** | `services/maps.py` | TomTom geocoding and neighborhood analysis |
| **Geocache** | `services/geocache.py` | Geocoding result cache |

### Infrastructure Services

| Service | File | Purpose |
|---------|------|---------|
| **Redis** | `services/redis.py` | Connection pool + cleanup |
| **Pub/Sub** | `services/pubsub.py` | Redis pub/sub wrapper |
| **Job Queue** | `services/job_queue.py` | Async job queue |
| **Logging** | `services/logging.py` | structlog setup |
| **Metrics** | `services/metrics.py` | Prometheus-style metrics export |
| **User Resolve** | `services/user_resolve.py` | Resolve user from request context |

---

## Domain Layer

**Location:** `domain/` — **pure-Python, side-effect free, deterministic, no I/O.**

The domain layer implements a layered projection pipeline. Each layer takes inputs and returns frozen dataclasses. No database queries, no Redis calls, no HTTP requests.

### Layer Pipeline

```
Events → Market → Actors → Reactions → Decisions → Outcomes → Reports
```

| Layer | Module | Key Types |
|-------|--------|-----------|
| **Events** | `domain/events.py` | `EventNamespace`, `canonical_event()` |
| **Market** | `domain/market/models.py` | `MarketContextSnapshot` (frozen dataclass with transit_score, safety_score, median_rent, inventory_pressure, etc.) |
| **Actors** | `domain/actors/` | `ActorSignalState`, `CohortSignalState`, `infer_actor_type()` |
| **Reactions** | `domain/reactions/` | `ReactionVector` (investor_optimism, willingness_to_transact, affordability_pressure, perceived_safety, displacement_concern), `ReactionEngine` |
| **Decisions** | `domain/decisions/` | `DecisionContext`, `DecisionRuntime`, policies (Negotiation, ListHold, Lease, Churn, DevResistance) |
| **Outcomes** | `domain/outcomes/` | `MarketOutcomeSnapshot`, projections (price movement, time-on-market, offer behavior) |
| **Reports** | `domain/reports/` | `UnderwritingReport`, `NegotiationBriefing`, `PolicyRiskBrief`, `ReplayNarrative` |

### Simulation Engine — `domain/simulation/`

Full market simulation loop with discrete steps:

| Module | Purpose |
|--------|---------|
| `models.py` | `SimulationState`, `SimulationConfig`, `StepResult` |
| `loop.py` | Main simulation loop: iterate steps until convergence or max rounds |
| `cohort_step.py` | Cohort-level market dynamics |
| `investor_step.py` | Investor behavior per round |
| `property_step.py` | Property-level price/status updates |
| `shocks.py` | External shock injection (market conditions, policy changes) |

### Decision Runtime Detail

```python
# DecisionPolicy is a Protocol:
class DecisionPolicy(Protocol):
    kind: str
    def evaluate(self, context: DecisionContext) -> DecisionRecommendation | None: ...

# DecisionRuntime aggregates multiple policies:
runtime = DecisionRuntime()
runtime.register(LeasePolicy())
runtime.register(ListHoldPolicy())
runtime.register(ChurnPolicy())

recommendations = runtime.evaluate(context)  # sorted by score DESC
top = runtime.top(context)                    # highest-scoring or None
```

Policies are lenient: if a policy raises, it's logged and skipped. The runtime never crashes.

---

## Agent Layer (Analyst Council)

**Files:** `agent/analyst_council.py`, `agent/analyst_personas.py`

This is **not** a chat agent. It's a structured analysis tool that runs parallel Claude calls to produce a listing score.

### How It Works

```
Property data
    │
    ▼
┌─────────────────────────────────────────────┐
│          Analyst Council                     │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Persona 1│  │ Persona 2│  │ Persona 3│  │    ← asyncio.gather (parallel)
│  │ ワンルーム │  │ アパート  │  │ ファミリー │  │
│  │ investor │  │ speculator│  │ buyer    │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │              │        │
│       ▼              ▼              ▼        │
│   AnalystVerdict AnalystVerdict AnalystVerdict│
│                                              │
│            Blend → overall_score             │
└──────────────────────────────────────────────┘
    │
    ▼
ListingAnalysis(overall_score, summary, verdicts[])
```

- Each persona gets 1 Claude API call (Haiku by default)
- Personas have JP prompts (`prompt_ja`) and titles (`title_ja`)
- Target: ≤5 Claude calls per listing analysis
- Verdicts are structured JSON with scores and rationale
- Overall score is a blended 0–100 rating

---

## Intelligence Layer

**Location:** `intelligence/` — pure-function financial calculations.

### Underwriting — `intelligence/underwriting.py`

```
underwrite(inputs: UnderwritingInputs) -> UnderwritingResult

Computes:
  - Monthly mortgage (amortization formula)
  - Effective gross income (rent × (1 - vacancy) × 12)
  - Annual NOI (gross income - opex - tax - insurance)
  - Cap rate = NOI / purchase_price
  - Cash-on-cash = (NOI - debt_service) / down_payment
  - DSCR = NOI / debt_service
  - Breakeven occupancy
  - IRR at 5-year and 10-year hold (bisection solver, no numpy)
```

### Stress Test — `intelligence/stress_test.py`

```
monte_carlo_stress_test(base, config) -> StressTestResponse

For N iterations (300–5000):
  1. Random draw within SliderRange for vacancy, rent_growth,
     expense_growth, loan_rate, exit_cap_rate
  2. Run underwriting with perturbed inputs
  3. Record cap_rate, CoC, DSCR, IRR

Output: percentiles (p10/p50/p90), tornado sensitivity,
        probability of negative cash flow
```

### JP Depreciation — `services/money_jp.py`

Statutory useful life (法定耐用年数) by construction type:

| Construction | Useful Life |
|-------------|-------------|
| Wood | 22 years |
| Light steel | 27 years |
| Steel | 34 years |
| RC | 47 years |
| SRC | 47 years |

Used in underwriting for tax shield calculations.

---

## Middleware

### Correlation ID — `middleware/correlation.py`

Every request gets a UUID stored in `contextvars`. This ID is:
- Extracted from `X-Correlation-ID` header (if present) or generated
- Added to response headers
- Threaded through all log entries, domain events, and agent decisions
- Accessible anywhere via `get_correlation_id()`

### Auth — `middleware/auth.py`

Supabase JWT verification (RS256 via JWKS endpoint):
- **Enabled** when `SUPABASE_JWT_ISSUER` and `SUPABASE_JWKS_URL` are both set
- **Disabled (passthrough)** when either is empty — useful for local dev and tests
- Validates `iss`, `aud`, `exp` claims
- Maps JWT `sub` to `UserProfile.supabase_user_id`

---

## Data Providers (JP)

### Provider Architecture

All external data providers follow the same pattern:
1. Protocol-based interface with `mock` and `live` modes
2. `httpx.AsyncClient` injection (tests use `MockTransport`)
3. tenacity retry + circuit breaker for live mode

### JP Data Providers — `services/providers_jp/`

| Provider | File | Data Source |
|----------|------|-------------|
| **REINS** | `providers_jp/reins.py` | Real Estate Information Network System — transaction data |
| **REINFOLIB** | `providers_jp/reinfolib.py` | MLIT Real Estate Information Library — transactions, land prices, appraisals, hazards |
| **e-Stat** | `providers_jp/estat.py` | 政府統計 — demographic and economic data |
| **Kokudo Suuchi** | `providers_jp/kokudo_suuchi.py` | 国土数値情報 — land price data |

### Signal Providers — `services/signal_providers/`

Pluggable market signal sources, registered in `registry.py`:

| Provider | Source | Signal Types |
|----------|--------|--------------|
| REINFOLIB Transaction | MLIT API | `median_sale_price` |
| REINFOLIB Land Price | MLIT API | `land_price` |
| REINFOLIB Appraisal | MLIT API | `appraisal_value` |
| REINFOLIB Hazard | MLIT API | `hazard` |
| e-Stat | 政府統計 API | `median_rent`, economic indicators |
| SUUMO Rent | SUUMO scrape | `median_rent` per area |
| Mock | Deterministic fixture | All signal types |

**Adding a new provider** (~50 lines):
1. Implement `MarketSignalProvider` Protocol (`name` property + `async fetch()`)
2. Register factory in `registry.py::_FACTORIES`
3. Mock HTTP with `httpx.MockTransport` in tests

---

## Market Signal Pipeline

```
External Sources (REINFOLIB, e-Stat, SUUMO)
    │
    ▼
scripts/fetch_external_signals.py  ──▶  Provider.fetch()
    │                                        │
    ▼                                        ▼
services/signal_writer.py::upsert_signal()
    │
    │  Idempotent per calendar day:
    │  same (signal_type, subject_type, subject_id) on same day → UPDATE
    │  different day → INSERT
    │
    ▼
db/models.py::MarketSignal table
    │
    ▼
services/market_state.py::build_snapshot(db, property_id)
    │
    │  Query latest signal per type for:
    │    1. Property-level signals (subject_id = property_id)
    │    2. Neighborhood signals (subject_id = neighborhood_id or zip_code)
    │  Property-level wins on overlap
    │
    ▼
domain/market/models.py::MarketContextSnapshot (frozen)
    │
    ▼
Consumed by: decisions, portfolio summary, property recommendations
```

---

## End-to-End Request Examples

### Example 1: Portfolio Summary with Recommendations

```
GET /api/portfolio/{portfolio_id}/summary
  │
  ▼
api/portfolio.py → services/portfolio_summary.py::build_portfolio_summary()
  │
  │  For each PortfolioHolding:
  │    ├─ Load HoldingFinancials from DB
  │    ├─ Load linked Property (if property_id set)
  │    ├─ services/holding_decision.py::compute_holding_decision()
  │    │    ├─ market_state.build_snapshot() → MarketContextSnapshot
  │    │    ├─ Derive ReactionVector from market + financials
  │    │    ├─ Build DecisionContext
  │    │    ├─ DecisionRuntime.evaluate() → [recommendations]
  │    │    └─ Return: HOLD | SELL | RAISE_RENT | REFI | IMPROVE
  │    └─ Build HoldingSummaryEntry
  │
  │  Aggregate:
  │    ├─ Sum financials (total_value, total_loan, cash_flow)
  │    ├─ Blended cap_rate, weighted DSCR
  │    ├─ Concentration by zip, asset_class_mix
  │    ├─ attention[] = holdings where recommendation ≠ HOLD
  │    └─ market_coverage stats
  │
  ▼
PortfolioSummaryReport → JSON response
```

### Example 2: Satei (Valuation) Compute

```
POST /api/satei/compute { city_code, menseki_m2, built_year, ... }
  │
  ▼
api/satei.py → services/satei_engine.py::compute_satei()
  │
  │  1. Query SaleComp by city_code or zip_code
  │  2. Filter: menseki_m2 ±30%, walk_minutes ±5
  │  3. Keep 3–20 most recent comps
  │  4. For each comp, compute adjustments:
  │     • Age: -0.5% per year older
  │     • Area: -0.3% per m² smaller
  │     • Walk: -1.0% per minute farther
  │     • Construction: SRC +5%, RC +3%, steel +1%, wood -2%
  │  5. Apply user overrides (if any)
  │  6. Weighted-average adjusted prices
  │  7. Confidence band from mean ± stdev
  │
  ▼
SateiResult → persist SateiSession → JSON response
```

### Example 3: Strategy Run (Async)

```
POST /api/strategy/run { portfolio_id, text }  → 202 Accepted
  │
  ▼
api/strategy.py
  │
  │  1. extract_strategy_profile(text) via Claude  → StrategyProfile
  │  2. start_strategy_run(portfolio_id, profile)  → run_id
  │  3. Background task: execute_strategy_run()
  │       ├─ build_portfolio_summary()
  │       ├─ Run simulation projections
  │       └─ reconcile_unified_report()
  │
  ▼
Client polls: GET /api/strategy/status/{run_id}
  → { status: "pending" | "running" | "complete" | "error", ... }
```

### Example 4: Listing Analysis (Analyst Council)

```
POST /api/listings/{listing_id}/analyze
  │
  ▼
api/listing_analysis.py → agent/analyst_council.py::review_listing()
  │
  │  1. Load Property from DB
  │  2. For each persona (3–4 analysts):
  │     ├─ Build context prompt (JP)
  │     ├─ Call Claude API (Haiku)     ← asyncio.gather (parallel)
  │     └─ Parse AnalystVerdict
  │  3. Blend verdicts → overall_score (0–100)
  │
  ▼
ListingAnalysis → JSON response
```

---

## Testing

**Framework:** pytest + pytest-asyncio, in-memory SQLite, fakeredis.

**Test fixtures** (`tests/conftest.py`):
- `db_session` — async SQLAlchemy session against `:memory:` SQLite
- JSONB columns patched to JSON type for SQLite compatibility
- fakeredis replaces real Redis
- No external API calls — providers use `httpx.MockTransport`

**Running tests:**
```bash
pytest tests/ -v --tb=short              # all tests
pytest tests/test_tier1_features.py -v   # single file
pytest tests/test_api_portfolio.py::test_create_portfolio  # single test
make test-cov                            # with coverage report
```

**Markers:** `@pytest.mark.unit`, `@pytest.mark.integration`

Integration tests (if added) go under `tests/integration/` and are skipped by default.
