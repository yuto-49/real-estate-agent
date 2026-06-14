# Simulation Engine

This document describes the simulation engines in the platform, their
architectural structure, the APIs they expose, the external data sources
they consume (including REINFOLIB), and how they integrate into the wider
system. It supersedes the previous `simulation-and-intelligence-architecture.md`
and `layered-market-knowledge-system.md`.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Simulation Flavors](#simulation-flavors)
   - [Unified Holding Simulation](#1-unified-holding-simulation)
   - [Market-Wide Investor Simulation](#2-market-wide-investor-simulation)
   - [Strategy Projection](#3-strategy-projection)
4. [Domain Layer — Pure Simulation Runtime](#domain-layer--pure-simulation-runtime)
5. [API Reference](#api-reference)
6. [External Data Sources & Signal Providers](#external-data-sources--signal-providers)
   - [REINFOLIB APIs (MLIT)](#reinfolib-apis-mlit)
   - [US Market Signal Providers](#us-market-signal-providers)
   - [Signal Pipeline Architecture](#signal-pipeline-architecture)
7. [Frontend Integration](#frontend-integration)
8. [Testing](#testing)

---

## Overview

The platform operates three simulation flavors, each serving a different
investment question:

| Simulation | Question It Answers | Scale | Engine |
|---|---|---|---|
| **Unified Holding** | "What happens to this property's NOI, DSCR, and cap rate under shocks?" | Single holding, up to 100 rounds | Pure-Python domain loop (`domain/simulation/`) |
| **Market-Wide Investor** | "How do different investor personas compete over a set of properties?" | N properties x M investors x T ticks | In-memory tick engine (`api/market_simulation.py`) |
| **Strategy Projection** | "Does my investment thesis survive a multi-year projection?" | Full portfolio, per-holding projection | Pure-Python rule engine (`services/strategy_runner.py`) |

All three are **deterministic**, **replay-able**, and produce **structured
output** suitable for dashboards, not free-text narratives.

---

## Architecture

```
                         ┌──────────────────────────┐
                         │   Frontend Components    │
                         │  MarketSimulationWorkspace│
                         │  PortfolioPage (tabs)    │
                         │  InvestmentPage sections │
                         └────────────┬─────────────┘
                                      │ REST API calls
                         ┌────────────▼─────────────┐
                         │        API Layer          │
                         │  simulation_unified.py    │
                         │  market_simulation.py     │
                         │  strategy.py              │
                         │  signals.py               │
                         └────────────┬─────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
   ┌──────────▼──────────┐ ┌─────────▼─────────┐ ┌──────────▼──────────┐
   │ Service Layer       │ │ Domain Layer       │ │ Intelligence Layer  │
   │ sim_orchestrator.py │ │ domain/simulation/ │ │ underwriting.py     │
   │ strategy_runner.py  │ │ domain/reactions/  │ │ stress_test.py      │
   │ market_state.py     │ │ domain/decisions/  │ │ tax_basic.py        │
   │ signal_writer.py    │ │ domain/outcomes/   │ │ financial_models.py │
   │ portfolio_summary.py│ │ (pure, no I/O)     │ └─────────────────────┘
   └──────────┬──────────┘ └───────────────────┘
              │
   ┌──────────▼──────────┐
   │ Signal Providers     │
   │ REINFOLIB (4 types) │
   │ FRED, Census, HUD   │
   │ FEMA, e-Stat, Mock  │
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │ PostgreSQL           │
   │ MarketSignal table   │
   │ PortfolioHolding     │
   │ HoldingFinancials    │
   └──────────────────────┘
```

### Key Boundaries

| Boundary | Rule |
|----------|------|
| `domain/simulation/` | Pure Python, side-effect free, deterministic. No DB, Redis, or HTTP. |
| `services/` | Orchestration. Bridges domain logic to DB and external APIs. |
| `api/` | Thin HTTP layer. Delegates to services and domain. |
| `intelligence/` | Financial computation. Receives data, returns results. No direct DB. |
| `services/signal_providers/` | External data fetch. Must inject `httpx.AsyncClient` for testability. |

---

## Simulation Flavors

### 1. Unified Holding Simulation

**Purpose:** Project a single holding's financial trajectory under configurable
policy shocks (rent decline, expense spike, regulation, transit disruption,
depreciation shield expiry).

**Entry point:** `POST /api/simulation/run`

**Pipeline (per round):**

```
1. Shock Translation
   PolicyShock → ReactionEvent tuple (domain/simulation/shocks.py)

2. Cohort Reaction Update
   Apply events to tenant cohorts' reaction vectors (cohort_step.py)

3. Churn Aggregation
   Derive occupancy impact from affordability + displacement pressure

4. Property State Update
   New NOI = (rent × occupancy) - opex ± shield
   New DSCR = NOI / debt_service

   New cap_rate = NOI / assessed_value

5. Investor Trace Update
   Recommendation: HOLD / SELL / REFI / IMPROVE
   Based on DSCR thresholds + investor sentiment

6. Replay Frame Build
   Round-by-round snapshot stored for replay

7. Convergence Check
   Break if NOI stable within threshold for 2 consecutive rounds
```

**Shock types and their effects:**

| Shock Type | Affected Variables | Direction |
|---|---|---|
| `rent_decline` | affordability_pressure (-3.0), investor_optimism (+2.0), willingness_to_transact (+1.5) | Tenants relieved, investor cautious |
| `expense_spike` | affordability_pressure (+2.0), investor_optimism (-1.5) | Stress on both sides |
| `transit_disruption` | perceived_safety (+2.0), trust_in_trajectory (+1.5), social_proof (+1.0) | Neighborhood quality drop |
| `rent_regulation` | affordability_pressure (-2.0), resistance_to_development (-1.0), investor_optimism (+3.0) | Tenant protection, investor signal |
| `shield_expiry` | investor_optimism (-0.3), willingness_to_transact (-0.15) | Depreciation shield loss |
| `custom` | Any variable via metadata | User-defined |

**Data flow:**

```
API Request (holding_id, shocks, max_rounds)
  → sim_orchestrator.build_sim_seed_from_holding(db, holding_id)
    → Loads PortfolioHolding + HoldingFinancials from DB
    → Constructs initial PropertyState, CohortState, InvestorTrace
  → domain/simulation/loop.run_simulation(config, seed)
    → Pure-Python loop, returns SimResult
  → API Response (recommendation, converged, final NOI/DSCR/cap_rate)
```

---

### 2. Market-Wide Investor Simulation

**Purpose:** Model how multiple investor personas compete to acquire
properties from a shared inventory over a configurable number of ticks.

**Entry point:** `POST /api/simulation/market/start`

**Investor archetypes and signal weights:**

| Archetype | Valuation | Yield | Neighborhood | Momentum | Risk Penalty |
|---|---|---|---|---|---|
| `value` | 0.35 | 0.25 | 0.15 | 0.05 | 0.20 |
| `yield` | 0.15 | 0.40 | 0.15 | 0.10 | 0.20 |
| `momentum` | 0.10 | 0.10 | 0.15 | 0.45 | 0.20 |
| `contrarian` | 0.40 | 0.20 | 0.10 | -0.10 | 0.20 |

**Cohort presets:** `balanced` (one of each), `income` (2x yield), `momentum`
(2x momentum).

**Tick simulation logic (`_simulate_tick`):**

For each property x investor pair per tick:

1. **Score** — weighted sum of valuation, yield, neighborhood, momentum
   metrics minus a risk penalty
2. **Decide** — `skip` (can't afford / low score), `watch` (score > 0.3),
   `bid` (score > 0.5 + tick x 0.02)
3. **Acquire** — highest-scoring bid > 0.55 wins; 20% of bid deducted
   from investor cash

**Persistence:** `MarketSimulationRun` + `MarketSimulationInvestor` tables
in PostgreSQL, plus in-memory `_store` for active runs.

---

### 3. Strategy Projection

**Purpose:** Take a user's free-text investment thesis, extract a structured
`StrategyProfile`, and project each portfolio holding forward by the
profile's hold period to test whether the strategy survives.

**Entry points:**
- `POST /api/strategy/extract` — free text to `StrategyProfile` (LLM-pluggable,
  heuristic fallback)
- `POST /api/strategy/run` — background job: analysis + simulation
- `GET /api/strategy/{run_id}/status` — poll
- `GET /api/strategy/{run_id}/result` — `UnifiedReport`

**Projection logic (pure-Python, no LLM):**

```python
projected_noi = current_noi * (1 + rent_growth - expense_growth) ** hold_years
projected_value = current_value * (1 + 0.03 + outlook_tilt) ** hold_years
```

Then re-runs a rule engine per holding:
- `SELL` if cash-flow collapse
- `REFI` if loan-rate outlook favorable
- `IMPROVE` / `HOLD` under tenant protection
- `RAISE_RENT` under explicit bias

**Output:** `UnifiedReport` with survival confidence, agreements (stable
recommendations), divergences (flipped recommendations), and per-holding
detail.

---

## Domain Layer — Pure Simulation Runtime

All code under `domain/` is **pure Python** — no I/O, no DB, no HTTP. This
enables fast testing, deterministic replay, and easy unit testing.

### Core Models (`domain/simulation/models.py`)

| Class | Fields |
|---|---|
| `PolicyShock` | round_num, shock_type, magnitude, label, metadata |
| `PropertyState` | occupancy_rate, effective_monthly_rent, monthly_opex, annual_noi, dscr, cap_rate, assessed_value |
| `CohortState` | cohort_label, size, reaction vector, churn_probability, affordability_pressure_avg |
| `InvestorTrace` | reaction vector, recommendation, recommendation_score, rationale |
| `SimConfig` | max_rounds, convergence_threshold, shocks tuple, base growth rates |
| `SimSeed` | initial property/cohorts/investor, depreciation shield info |
| `SimResult` | config, seed, rounds tuple, converged flag, final states |

### Reaction Vector (`domain/reactions/models.py`)

Eight normalized variables in [-1, 1] that drive actor behavior:

| Variable | Meaning |
|---|---|
| `trust_in_trajectory` | Confidence in neighborhood direction |
| `affordability_pressure` | Cost burden on tenants |
| `perceived_safety` | Neighborhood safety perception |
| `social_proof` | "Everyone is buying/fleeing" effect |
| `displacement_concern` | Fear of being priced out |
| `investor_optimism` | Investor sentiment |
| `willingness_to_transact` | Market liquidity |
| `resistance_to_development` | Community pushback |

### Step Functions

| Function | File | Purpose |
|---|---|---|
| `translate_shock()` | `shocks.py` | PolicyShock to ReactionEvent tuple |
| `update_cohorts()` | `cohort_step.py` | Apply events to tenant reaction vectors, derive churn |
| `update_property()` | `property_step.py` | Compute new NOI, DSCR, cap rate from churn + growth |
| `update_investor()` | `investor_step.py` | Derive recommendation from DSCR + sentiment |
| `run_simulation()` | `loop.py` | Main loop composing all steps |

### Decision Policies (`domain/decisions/`)

The `DecisionRuntime` runs pluggable policies to produce investor
recommendations. Five built-in policies:

| Policy | Recommends |
|---|---|
| `NegotiationPolicy` | Buy/wait/walk on transaction terms |
| `ListHoldPolicy` | List vs hold based on market signals |
| `LeasePolicy` | Raise rent, hold, improve based on lease metrics |
| `ChurnPolicy` | Tenant retention actions |
| `DevResistancePolicy` | Community sentiment risk |

Used by the Decisions tab (`api/decisions.py`), Portfolio Summary
(`services/portfolio_summary.py`), and Strategy Runner
(`services/strategy_runner.py`) — all three surfaces agree per-holding.

---

## API Reference

### Unified Holding Simulation — `/api/simulation/`

| Method | Path | Description | Request | Response |
|---|---|---|---|---|
| POST | `/run` | Run simulation for a holding | `SimRunRequest` (holding_id, shocks, max_rounds, convergence_threshold) | `SimRunResponse` (run_id, status, recommendation, converged, final NOI/DSCR/cap_rate) |
| GET | `/{run_id}/replay` | Round-by-round replay data | — | `ReplayResponse` (rounds array with NOI, occupancy, shocks, churn) |

### Market Simulation — `/api/simulation/market/`

| Method | Path | Description | Request | Response |
|---|---|---|---|---|
| POST | `/personas` | Generate synthetic investor personas | `MarketSimulationPersonaRequest` (scope, cohort_preset, investor_count) | `MarketSimulationPersonaResponse` (personas, inventory summary) |
| POST | `/start` | Launch tick-based simulation | `MarketSimulationStartRequest` (personas, tick_count, run_label) | `MarketSimulationStartResponse` (run_id, status) |
| GET | `/status/{id}` | Poll progress | — | `MarketSimulationStatusResponse` (progress %, current tick) |
| GET | `/result/{id}` | Final results | — | `MarketSimulationResultResponse` (acquisitions, investor outcomes) |
| GET | `/replay/{id}` | Full tick-by-tick replay | — | `MarketSimulationReplayResponse` (ticks, property states, investor decisions) |
| POST | `/handoff-to-negotiation` | Bridge to negotiation engine | `MarketSimulationHandoffRequest` | (stub — not yet reimplemented) |

### Strategy — `/api/strategy/`

| Method | Path | Description | Request | Response |
|---|---|---|---|---|
| POST | `/extract` | Free text to StrategyProfile | `{ text: string }` | `StrategyProfile` (assumptions, policy, thesis) |
| POST | `/run` | Launch background strategy run | `{ portfolio_id, profile, ... }` | `{ run_id, status }` |
| GET | `/{run_id}/status` | Poll run progress | — | `{ status, progress }` |
| GET | `/{run_id}/result` | Get unified report | — | `UnifiedReport` (survives, agreements, divergences, per-holding) |

### Investment Analysis — `/api/underwrite/`

| Method | Path | Description |
|---|---|---|
| POST | `/` | Single-deal underwriting (cap rate, CoC, DSCR, IRR) |
| POST | `/stress-test` | Monte Carlo over 5 sliders: p10/p50/p90 bands |

### Portfolio — `/api/portfolio/`

| Method | Path | Description |
|---|---|---|
| POST | `/` | Create portfolio |
| POST | `/{id}/holdings` | Add holding |
| GET | `/{id}/aggregate` | Blended cap rate, DSCR, equity, mix |
| GET | `/{id}/summary` | Full consolidated report (Overview tab) |
| DELETE | `/{id}/holdings/{hid}` | Remove holding |

### Decisions — `/api/decisions/`

| Method | Path | Description |
|---|---|---|
| GET | `/holding/{hid}` | DecisionRuntime: HOLD / RAISE_RENT / REFI / SELL / IMPROVE |

### Signals — `/api/signals/`

| Method | Path | Description |
|---|---|---|
| GET | `/reinfolib` | Latest REINFOLIB + market signals for a zip code |

Query params: `zip_code` (required), `types` (optional, comma-separated).

Returns a flat snapshot: `{ zip_code, signals_count, median_sale_price, land_price_psm, hazard_flood, ... }`

### Market Context — `/api/properties/`

| Method | Path | Description |
|---|---|---|
| GET | `/{id}/market-context` | `MarketContextSnapshot` for a property |

### Listing Analysis — `/api/listings/`

| Method | Path | Description |
|---|---|---|
| POST | `/analyze` | Analyze a listing (comps, underwriting) |
| GET | `/reports` | List analysis reports |

### Rent Comps — `/api/properties/`

| Method | Path | Description |
|---|---|---|
| GET | `/{id}/rent-comps` | Comparable rental data for a property |

### Stubs (501 — features removed in Tokyo pivot)

| Prefix | Original Purpose |
|---|---|
| `/api/negotiations` | Buyer/seller negotiation sessions |
| `/api/reports` | MiroFish report generation |
| `/api/social-sim` | Social sentiment simulation |
| `/api/visualization` | Visualization replay |
| `/api/agent` | AI agent chat |
| `/ws/negotiations/{id}` | Negotiation WebSocket |
| `/ws/strategy/{run_id}` | Strategy WebSocket |

---

## External Data Sources & Signal Providers

All external data enters the system through the **Signal Provider** pattern:
implement the `MarketSignalProvider` Protocol, register in
`services/signal_providers/registry.py`, and the shared `signal_writer`
handles idempotent persistence.

### REINFOLIB APIs (MLIT)

REINFOLIB is the Japanese Ministry of Land, Infrastructure, Transport and
Tourism's real estate data API. All REINFOLIB endpoints require an
`Ocp-Apim-Subscription-Key` header.

**Base URL:** `https://www.reinfolib.mlit.go.jp/ex-api/external`

**Config:** `REINFOLIB_API_KEY` in `.env`

| Provider | Endpoint | Signal Type | Subject | Description |
|---|---|---|---|---|
| `reinfolib_transaction` | **XIT001** | `median_sale_price`, `median_unit_price` | Municipality (5-digit code) | Real estate transaction prices. Aggregates individual sales per city/year/quarter into median values. Defaults to Tokyo 23 wards. |
| `reinfolib_land_price` | **XPT002** | `land_price_psm` | Survey point ID | Land price survey points (GeoJSON tiles). Returns price/m2, zoning, FAR/BCR, station distance, YoY change. Uses XYZ tile coordinates at zoom 14. |
| `reinfolib_appraisal` | **XCT001** | `appraised_value_psm` | Address or lat/lng | Government-appraised valuations per parcel. Carries ~60 metadata fields (zoning, road access, utilities, transit). Defaults to Tokyo (prefecture 13). |
| `reinfolib_hazard` | **XKT025**, **XKT026**, **XKT029** | `hazard_liquefaction`, `hazard_flood`, `hazard_landslide` | Mesh code or tile key | Natural disaster risk layers. Liquefaction (6-level, 0-10 score), flood inundation depth (category, 0-10 score), landslide warning zones (binary 0/8). |

**Shared utilities** (`services/signal_providers/reinfolib_base.py`):
- `reinfolib_get()` — authenticated GET with 404-as-None handling
- `lat_lng_to_tile()` / `tiles_covering_bbox()` — Web Mercator tile math
- `TOKYO_23_BBOX` / `TOKYO_23_CITY_CODES` — default geographic scope

**REINFOLIB tile coordinate system:**

The XPT and XKT endpoints use XYZ tile coordinates (Web Mercator /
EPSG:3857). The `reinfolib_base` module provides conversion functions:

```
lat/lng → lat_lng_to_tile(lat, lng, zoom) → (x, y) tile
bounding box → tiles_covering_bbox(min_lat, min_lng, max_lat, max_lng, zoom) → [(x, y), ...]
```

**How REINFOLIB signals are consumed:**

```
REINFOLIB API
  → ReinfolibXxxProvider.fetch()       # httpx async, returns ExternalSignal[]
  → signal_writer.upsert_signal()      # idempotent per calendar day
  → MarketSignal table (PostgreSQL)
  → build_snapshot(db, property_id)    # services/market_state.py
  → MarketContextSnapshot              # domain/market/
  → Consumed by: simulation, decisions, underwriting, portfolio summary, frontend
```

### Other JP Signal Providers

| Provider | Config Key | Signal Type | Source |
|---|---|---|---|
| `estat` | `ESTAT_APP_ID` | various | Japanese e-Stat government statistics |

### Signal Pipeline Architecture

```
┌──────────────────────────────────────────────────────────┐
│  scripts/fetch_external_signals.py --source <name>       │
│  scripts/backfill_market_signals.py                      │
│  (or any service-layer caller)                           │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  registry.get_provider(name) → MarketSignalProvider      │
│  provider.fetch(**kwargs) → Sequence[ExternalSignal]      │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  signal_writer.upsert_signal(db, signal)                 │
│  - Same calendar day + (signal_type, subject_type,       │
│    subject_id) → UPDATE existing row                     │
│  - Different day → INSERT new row                        │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  MarketSignal table (db/models.py)                       │
│  Columns: signal_type, subject_type, subject_id,         │
│           value, payload (JSONB), recorded_at            │
└──────────────────────────────────────────────────────────┘
```

**Adding a new provider** requires ~50 lines:

1. Create a class implementing `MarketSignalProvider` Protocol (has `name: str`
   and `async fetch(...)` method)
2. Register a factory in `_FACTORIES` dict in `registry.py`
3. Mock HTTP calls with `httpx.MockTransport` in tests
4. See `doc/market-signal-sources.md` for candidate data sources

---

## Frontend Integration

### Simulation Workspace Components

| Component | File | Purpose |
|---|---|---|
| `MarketSimulationWorkspace` | `components/MarketSimulationWorkspace.tsx` | Full market simulation UI: configure, generate personas, run, replay |
| `SimulationSummaryPanel` | `components/SimulationSummaryPanel.tsx` | Aggregate metrics (acquisitions, market temperature) |
| `SimulationPersonaCard` | (inline) | Display investor persona (archetype, budget, signals) |
| `MarketSimulationMap` | (inline) | Geographic visualization of properties + investors |
| `PropertySimulationMap` | `components/PropertySimulationMap.tsx` | Property-level map layer |

### Investment Page Sections

| Section | Component | APIs Consumed |
|---|---|---|
| Dashboard | `DashboardSection` | `GET /api/portfolio/{id}/summary` |
| Portfolio | `PortfolioSection` | `GET /api/portfolio/{id}/holdings`, `GET /api/decisions/holding/{id}` |
| Analysis | `AnalysisSection` | `POST /api/listings/analyze`, `GET /api/listings/reports` |
| Simulation | `SimulationSection` | Market: `POST .../market/personas` then `/market/start` then `/market/replay`; Property: `POST .../run` |
| Strategy | `StrategySection` | `POST /api/underwrite/run`, `POST /api/strategy/run` |

### Custom Hooks

| Hook | File | Purpose |
|---|---|---|
| `useSimulationReplay` | `hooks/useSimulationReplay.ts` | Replay playback state (play/pause/speed/round navigation) |
| `useMarketContext` | `hooks/useMarketContext.ts` | Fetch and cache market signals for a property or zip |

### Market Data Component

`MarketDataCard` (`components/invest/MarketDataCard.tsx`) displays REINFOLIB
signals fetched via `GET /api/signals/reinfolib?zip_code=...`. Shows land
price, appraised value, transaction medians, and hazard indicators.

---

## Testing

All simulation tests run in-memory with no external services required.

| Test File | Coverage |
|---|---|
| `tests/test_simulation_loop.py` | Full simulation run, rent decline shock, shield expiry, replay frames |
| `tests/test_simulation_models.py` | Model instantiation + schema validation |
| `tests/test_simulation_property_step.py` | Property state updates (occupancy, NOI, DSCR) |
| `tests/test_simulation_cohort_step.py` | Cohort reaction + churn derivation |
| `tests/test_simulation_investor_step.py` | Investor recommendation logic |
| `tests/test_simulation_shocks.py` | Shock-to-event translation |
| `tests/test_reinfolib_providers.py` | REINFOLIB signal providers (mocked HTTP) |
| `tests/test_providers_jp_reinfolib.py` | JP REINFOLIB provider fixtures |

**Testing pattern for providers:**

```python
# Mock the HTTP layer, verify signal output
transport = httpx.MockTransport(handler)
client = httpx.AsyncClient(transport=transport)
provider = ReinfolibTransactionProvider(client=client, api_key="test")
signals = await provider.fetch(year=2024, quarter=1)
assert signals[0].signal_type == "median_sale_price"
```

Run all tests:

```bash
pytest tests/ -v                                          # full suite
pytest tests/test_simulation_loop.py -v                   # simulation only
pytest tests/test_reinfolib_providers.py -v               # REINFOLIB only
```
