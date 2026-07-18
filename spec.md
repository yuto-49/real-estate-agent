# Project Specification — Real Estate Agentic System

> **Purpose of this document.** This is a single, self-contained specification of the
> entire project. It is written so that a person — or an LLM with no prior context —
> can read it top to bottom and understand what the system is, why it exists, how it is
> built, every module and endpoint, the data model, the financial math, the AI usage,
> the frontend, and the conventions that govern the code. Paste it into a blank chat and
> the model will "understand everything."

---

## 1. Elevator Pitch

**Real Estate Agentic System** is a **Tokyo workforce-housing investor-analytics
platform**. It helps a real-estate investor underwrite, monitor, and forward-simulate a
portfolio of residential rental properties — with first-class support for the Japanese
market (one-room mansions, アパート, family mansions) and its tax/depreciation rules.

The product is **not** a chatbot and **not** a consumer listings site. It is an
**analytics surface** built around a portfolio of holdings. The three things it does:

1. **Underwrite** — compute the ground-truth financials of a property or holding
   (cap rate, cash-on-cash, DSCR, IRR, breakeven occupancy, Monte-Carlo stress tests).
2. **Intelligence** — ingest real-world **market signals** (crime, rents, mortgage
   rates, flood hazard, census data) and fold them into a market-context snapshot per
   property/neighborhood.
3. **Simulate** — take a free-text investment thesis, extract a structured strategy
   profile, and project the portfolio forward, reconciling per-holding survival and
   confidence.

**Stack:** FastAPI (async Python 3.11+) backend · React 18 + TypeScript + Vite frontend
· PostgreSQL (asyncpg) · Redis (pub/sub + cache + job queue) · Supabase auth (JWT/JWKS)
· Claude API (Anthropic) for listing analysis and free-text → structured extraction.

### Domain focus
**Workforce housing** — affordable, accessible housing for essential workers and
moderate-income households — with emphasis on regulatory compliance and
market-signal-driven intelligence.

### ⚠️ Post-pivot scope (important historical context)
The project began as a buyer/seller **negotiation chat** product with a social-sentiment
**NIMBY simulator**, a synthetic **market-tick engine**, and a **MiroFish** free-text
report flow. **All four were removed.** Alembic migration `f9a1b2c3d4e5` dropped their
**15 tables**; the frontend surface and dead schemas were deleted afterward.

What survived and now powers the investor product:
- The **layered domain runtime** (`domain/`) — a pure-Python market→actor→reaction→
  decision→outcome→report pipeline.
- The **market-signal pipeline** (providers + `market_signals` table + snapshot builder).

A few **vestiges** remain and should be treated as dormant/legacy, not active product:
- `api/schemas.py` still defines `MarketSimulation*`, `Offer*`, `ConversationEvent`,
  `SimulationReplay*` Pydantic models (no live routers consume most of them).
- `domain/decisions/negotiation.py` is a complete negotiation state-machine primitive
  with **no product consumer**.
- `intelligence/financial_models.py` is legacy and **unreferenced**.
- Several `config.py` settings (`mirofish_*`, `max_simulation_rounds`,
  `max_batch_scenarios`, `min_offer_percent`, `max_counter_rounds`, `max_deal_value_auto`)
  have **no consumers** after the negotiation removal.

---

## 2. Technology Stack

### Backend (`pyproject.toml`, package name `real-estate-agent`, version `0.1.0`)
| Concern | Choice |
|---|---|
| Language | Python ≥ 3.11, full type hints |
| Web framework | FastAPI ≥ 0.115, Uvicorn (standard) |
| AI | `anthropic` ≥ 0.52 (Claude) |
| ORM | SQLAlchemy 2.0 async style + asyncpg |
| Schemas/config | Pydantic v2 + pydantic-settings |
| HTTP client | httpx (async; tests use `httpx.MockTransport`) |
| Cache/PubSub | redis[hiredis] ≥ 5 (async client) |
| Migrations | Alembic (async engine) |
| Resilience | tenacity (retry/backoff on external calls) |
| Auth | PyJWT[crypto] (RS256 via JWKS) |
| Geo | geohash2 (cache keys) |
| Logging | structlog (JSON, correlation-id bound) — **never `print`** |
| Lint/type | ruff (line length 100, rules E/F/I/N/W/UP), mypy |
| Tests | pytest, pytest-asyncio (`asyncio_mode = auto`), pytest-cov, fakeredis |

### Frontend (`frontend/package.json`)
| Concern | Choice |
|---|---|
| Framework | React 18.3 + TypeScript 5.6 |
| Build | Vite 6 (`tsc && vite build`) |
| Routing | react-router-dom 6 |
| Maps | maplibre-gl 4 + supercluster 8 (clustered property map) |
| Auth | @supabase/supabase-js 2 |
| Unit tests | Vitest 4 + @testing-library/react + jsdom |
| E2E | Playwright |

---

## 3. Repository Layout

```
real-estate-agent/
├── main.py                  # FastAPI entry point; mounts all routers + middleware
├── config.py                # pydantic-settings Settings (reads .env)
├── pyproject.toml           # deps, ruff, pytest config
├── CLAUDE.md                # guidance for AI coding agents (authoritative architecture notes)
├── README.md
├── spec.md                  # ← this document
│
├── api/                     # FastAPI routers + Pydantic schemas
│   ├── schemas.py           # ALL request/response models (Pydantic v2)
│   ├── properties.py  search.py  users.py  portfolio.py  underwrite.py
│   ├── listing_analysis.py  decisions.py  strategy.py  onboarding.py
│   ├── investor_profile.py  public_config.py
│
├── db/
│   └── models.py            # 9 SQLAlchemy models + 10 enums; UUID/String PKs, JSONB cols
│
├── services/                # business logic + ALL I/O (DB, Redis, HTTP, Claude)
│   ├── event_store.py       # the ONLY domain_events writer
│   ├── portfolio_summary.py strategy_runner.py unified_report.py strategy_profile.py
│   ├── holding_decision.py  market_state.py  signal_writer.py
│   ├── portfolio_chat_extractor.py  listing_import.py  property_recommender.py
│   ├── market_data.py  market_data_provider.py  maps.py  geocache.py
│   ├── redis.py  pubsub.py  job_queue.py  metrics.py  logging.py  user_resolve.py
│   ├── address_jp.py  money_jp.py            # Japan helpers
│   ├── signal_providers/    # pluggable external market-signal sources (Protocol-based)
│   └── providers_jp/        # Japan data sources (currently fixture-only mocks)
│
├── domain/                  # PURE-PYTHON layered runtime — no I/O, deterministic, lenient
│   ├── events.py            # canonical event taxonomy
│   ├── market/  actors/  reactions/  decisions/  outcomes/  reports/
│
├── intelligence/            # financial math
│   ├── underwriting.py  stress_test.py  tax_basic.py  depreciation_jp.py
│   └── financial_models.py  # LEGACY / unreferenced
│
├── agent/                   # Claude-driven listing-analysis council
│   ├── analyst_council.py  analyst_personas.py
│
├── middleware/
│   ├── correlation.py  auth.py  rate_limit.py
│
├── alembic/versions/        # 14 migrations; head = f9a1b2c3d4e5
├── scripts/                 # DB init, seeds, signal backfill/fetch, dev user
├── tests/                   # ~51 pytest files (in-memory SQLite, fakeredis)
└── frontend/                # React 18 + TS + Vite SPA
    └── src/{pages,components,auth,hooks,utils,config}
```

**File-organization principle (project rule):** many small focused files (200–400 lines
typical, 800 max), organized by feature/domain not by type; immutable data (frozen
dataclasses / new copies, never in-place mutation).

---

## 4. Architecture Overview

```
React SPA  ──HTTP/JSON──▶  FastAPI (api/)  ──▶  services/  ──▶  PostgreSQL + Redis
(Portfolio page =          │  routers           (business logic + I/O)      │
 center of gravity)        │                         │                      ▼
                           │                         ▼            domain_events (event-sourced
                           │                  domain/ (pure projections,     audit, correlation id)
                           ▼                  no I/O): market → actor →
                  middleware (correlation,    reaction → decision →
                  auth JWT, rate limit)       outcome → report
                                                         │
                                              Redis pub/sub (live strategy-run step events)

Claude API: agent/analyst_council (listing analysis) + services/portfolio_chat_extractor
            (free-text portfolio import). services/strategy_profile is heuristic today.
```

### Request lifecycle
1. Every request gets a **correlation-id UUID** from `middleware/correlation.py`
   (a contextvar; background tasks must capture it at request time — it does not
   propagate automatically).
2. `middleware/auth.py` validates the Supabase JWT (RS256 via JWKS). **Auth is
   passthrough/disabled** when `SUPABASE_JWT_ISSUER` / `SUPABASE_JWKS_URL` are empty
   (useful for tests and bare-DB dev).
3. `middleware/rate_limit.py` applies rate limiting.
4. Router → service → (optional) pure `domain/` projection → DB/Redis.
5. State-changing flows **append to `domain_events`** via `EventStore.append`.

### Layering rules (enforced conventions)
- **`domain/` is pure:** side-effect free, deterministic, no DB/Redis/Claude. Inputs in,
  frozen dataclasses out.
- **`domain/` is lenient:** missing/unknown data → warn + sensible default (`None`/zero),
  **never raise**. (`ValueError` is reserved for the dormant negotiation state machine.)
- **`services/` owns all I/O** and orchestration.
- **`EventStore.append` is the only writer to `domain_events`.**
- **`signal_writer.upsert_signal` is the only writer to `market_signals`** — never
  `db.add(MarketSignal(...))` from new code.

---

## 5. Data Model (`db/models.py`)

PostgreSQL with asyncpg; UUID/String primary keys; JSONB columns for flexible structured
data. Tests swap in in-memory SQLite (JSONB→JSON patched).

### 5.1 Enums
| Enum | Values |
|---|---|
| `LifeStage` | FIRST_TIME, RELOCATING, INVESTOR, DOWNSIZING, UPGRADING |
| `RiskTolerance` | LOW, MODERATE, HIGH |
| `PropertyStatus` | ACTIVE, PENDING, SOLD, WITHDRAWN |
| `PortfolioMode` | INSTITUTIONAL, INDIVIDUAL (top-nav UI mode toggle) |
| `InvestmentStrategy` | BUY_HOLD, BRRRR, FIX_FLIP, MIXED |
| `AssetClass` | SFR, MF_2_4, MF_5_PLUS, CONDO, TOWNHOUSE |
| `HoldingStatus` | HELD, UNDER_REHAB, LISTED, SOLD |
| `AssetTier` (JP) | ONE_ROOM, APARUTO, FAMILY_MANSION |
| `ConstructionType` (JP) | WOOD (22yr), LIGHT_STEEL (27yr), STEEL (34yr), RC (47yr), SRC (47yr) |
| `SeismicCode` (JP) | KYU_TAISHIN (pre-1981-06), SHIN_TAISHIN (1981-06+) |

### 5.2 Models (9 tables)
1. **UserProfile** (`user_profiles`) — id, `supabase_user_id` (unique, links auth),
   name, email (unique), role (default "buyer"), budget_min/max, life_stage,
   risk_tolerance (default MODERATE), investment_goals (JSONB), timeline_days (90),
   lat/lng, zip_code, search_radius (10), preferred_types (JSONB), preferred_mode
   (default INSTITUTIONAL), timestamps.
2. **Property** (`properties`) — id, seller_id→UserProfile, address, lat/lng,
   asking_price, bedrooms, bathrooms, sqft, property_type, hoa_fees, status (ACTIVE),
   neighborhood_data/disclosures (JSONB). **JP columns:** address_jp, nearest_stations,
   built_year, structure, youto_chiiki (用途地域/zoning), kenpei_ritsu (建蔽率),
   youseki_ritsu (容積率), menseki_m2 (面積), baibai_kakaku_yen (売買価格),
   kanrihi_yen (管理費), shuuzenzumitatekin_yen (修繕積立金),
   takken_bukken_bangou, hazard_flags, currency (JPY), jurisdiction (us).
   **JP Phase 2A tier columns:** asset_tier, construction_type, seismic_code,
   re_buildable (再建築可否), road_frontage_m, ward_code, walk_minutes_to_station,
   assumed_monthly_rent_yen, occupancy_rate.
3. **DomainEvent** (`domain_events`, append-only) — id, correlation_id, event_type,
   aggregate_type, aggregate_id, sequence, payload (JSONB), actor_type, actor_id.
   Indexed by (aggregate_type, aggregate_id) and (correlation_id). **Event-sourced audit.**
4. **MarketSignal** (`market_signals`) — id, signal_type, subject_type
   (property|neighborhood|jurisdiction), subject_id, value (Float), payload (JSONB),
   source, observed_at, created_at. Indexed by (subject_type, subject_id) and
   (signal_type, observed_at). **Only persistence added for the domain runtime.**
5. **InvestorPortfolio** (`investor_portfolios`) — id, user_id→UserProfile, name,
   investment_strategy (BUY_HOLD), notes, timestamps.
6. **PortfolioHolding** (`portfolio_holdings`) — id, portfolio_id→InvestorPortfolio,
   property_id→Property (**nullable** — allows tracking off-platform properties),
   address, lat/lng, zip_code, asset_class (SFR), status (HELD), acquisition_date.
7. **HoldingFinancials** (`holding_financials`) — id, holding_id→PortfolioHolding,
   cost_basis, current_value_estimate, value_estimate_source, loan_balance,
   interest_rate, loan_maturity, monthly_piti, monthly_rent, vacancy_rate (0.05),
   monthly_opex_estimate, property_tax_annual, insurance_annual.
8. **InvestorProfile** (`investor_profiles`) — id, user_id→UserProfile (unique), budget,
   strategy, target_cap_rate, target_coc, geography (JSONB), notes, timestamps.
9. **UnderwritingScenario** (`underwriting_scenarios`) — id, holding_id (nullable),
   correlation_id, label, inputs (JSONB), outputs (JSONB), hazard_signals (JSONB).

### 5.3 Relationships
```
UserProfile
 ├─▶ InvestorPortfolio (user_id)
 │     └─▶ PortfolioHolding (portfolio_id)
 │           ├─▶ Property (property_id, nullable)
 │           ├─▶ HoldingFinancials (holding_id)
 │           └─▶ UnderwritingScenario (holding_id, nullable)
 └─▶ InvestorProfile (user_id, unique)
Property ─▶ UserProfile (seller_id);  MarketSignal keyed by subject_id/subject_type
DomainEvent: append-only audit (no FK)
```

---

## 6. API Surface

All routers mounted in `main.py` under `/api` (title "Real Estate Agentic System",
version 0.2.0). CORS allows `http://localhost:5173`. Middleware order:
`CorrelationIdMiddleware` then CORS.

### `/api/properties`
| Method · Path | Purpose |
|---|---|
| `GET /` | List properties (→ `PropertyListResponse`) |
| `GET /recommend` | Deterministic property recommendations (→ `PropertyRecommendationsResponse`) |
| `GET /{id}` | Single property (→ `PropertyResponse`) |
| `GET /{id}/market-context` | Wraps `market_state.build_snapshot` → `MarketContextSnapshot` JSON |
| `POST /` | Create property (201) |
| `PATCH /{id}` | Update property |

### `/api/search`
| `GET /` | Property search |

### `/api/users`
| `POST /` (201) · `GET /{id}` · `PATCH /{id}` · `DELETE /{id}` (204) · `GET /` | User CRUD |

### `/api/portfolio` — the product's core router
| Method · Path | Purpose |
|---|---|
| `POST /` (201) | Create portfolio (→ `InvestorPortfolioResponse`) |
| `GET /` | List portfolios |
| `GET /{portfolio_id}` | Get one |
| `DELETE /{portfolio_id}` (204) | Delete |
| `POST /{portfolio_id}/holdings` | Add holding |
| `GET /{portfolio_id}/holdings` | List holdings |
| `GET /{portfolio_id}/holdings/{holding_id}` | Get holding |
| `DELETE /{portfolio_id}/holdings/{holding_id}` (204) | Remove holding |
| `GET /import/csv/template` | CSV template download |
| `POST /import/csv` | Bulk import holdings from CSV |
| `POST /import/chat` | **Claude** free-text → structured holdings (`ChatImportResponse`) |
| `POST /import/chat/confirm` | Persist the chat-extracted holdings |
| `POST /from-property` | Create a holding from an on-platform property |
| `GET /{portfolio_id}/aggregate` | Roll-up totals (→ `PortfolioAggregateResponse`) |
| `GET /{portfolio_id}/summary` | **Analysis tab** payload (→ `PortfolioSummaryReport`) |

### `/api/underwrite`
| `POST ""` → `UnderwriteResponse` | Single-property DCF underwriting |
| `POST /stress-test` → `StressTestResponse` | Monte-Carlo sensitivity |

### `/api/listing`
| `POST /parse` → `ListingParseResponse` | Parse a Zillow URL into structured fields (no scraping) |

### `/api/listings` (listing-analysis)
| `POST /{listing_id}/analyze` → `ListingAnalysisResponse` | **Claude** multi-persona analyst council |

### `/api/decisions`
| `GET /holding/{holding_id}` → `HoldingDecisionResponse` | Per-holding decision (hold/raise-rent/refi/sell/improve) via `holding_decision` + `domain/decisions` |

### `/api/strategy` — the Simulation pipeline
| `POST /extract` → `StrategyExtractResponse` | Free-text → `StrategyProfile` (heuristic) |
| `POST /run` → `StrategyRunStartResponse` | Kick off a forward simulation run |
| `GET /recent` → `list[StrategyRunRecord]` | Recent runs |
| `GET /{run_id}/status` → `StrategyRunRecord` | Poll run status (+ live step events over Redis) |
| `GET /{run_id}/result` → `StrategyRunRecord` | Final result (SimulationReport + UnifiedReport) |

### `/api/onboarding`
| `GET /state` → `OnboardingStateResponse` | Onboarding progress/gating |

### `/api/investor-profile`
| `POST /` (201) · `GET /` → `InvestorProfileResponse` | Upsert / read investor profile |

### `/api/config`
| `GET /public` → `PublicRuntimeConfigResponse` | Public runtime config for the SPA (Supabase URL, map style, API base) |

### Key schemas (`api/schemas.py`)
~90 Pydantic models. The central ones:
- **UnderwriteRequest / UnderwriteResponse** — DCF inputs and results (mirrors
  `intelligence.underwriting`).
- **StressTestRequest / StressTestConfigSchema / SliderRangeSchema / StressTestResponse**
  — Monte-Carlo config + percentile/tornado results.
- **StrategyProfile** (+ `StrategyAssumptions`, `StrategyPolicyConfig`, `StrategyThesis`) —
  the extracted, user-overridable assumptions that drive simulation.
- **PortfolioSummaryReport** (+ `HoldingSummaryEntry`, `PortfolioAttentionItem`,
  `MarketCoverage`, `PortfolioSummaryAggregates`) — the Analysis-tab payload.
- **SimulationReport** (`HoldingProjection[]`) + **UnifiedReport**
  (`HoldingReconciliation[]`) — simulation outputs + survival/confidence reconciliation.
- **StrategyRunRecord / StrategyRunStep** — run audit record with step timeline.
- Legacy/dormant (negotiation-era, mostly unconsumed): `MarketSimulation*`, `Offer*`,
  `ConversationEvent`, `SimulationReplay*`, `DomainEventResponse`.

---

## 7. Services Layer (`services/`)

All business logic and I/O. Highlights:

### Investor pipeline (the heart)
| Module | Responsibility |
|---|---|
| `portfolio_summary.py` | `build_portfolio_summary` — the `/summary` aggregator; per-holding cap rate / DSCR / CoC / recommendation + attention list + aggregates. Also seeds strategy analysis. |
| `strategy_runner.py` | In-process run store; `execute_strategy_run` (orchestration, audited to `domain_events`, emits Redis step events); pure `project_simulation` (forward projection — **profile-driven, currently signal-blind**). |
| `unified_report.py` | `reconcile_unified_report` — merges summary + simulation into per-holding survival/confidence reconciliation. |
| `strategy_profile.py` | `extract_strategy_profile` — free-text → `StrategyProfile`. **Heuristic today, LLM-pluggable.** No Claude call currently. |
| `holding_decision.py` | `compute_holding_decision` — bridges a holding into `domain/decisions` policies → recommendation (live consumer of the decision runtime). |
| `portfolio_chat_extractor.py` | **Claude** tool-use extraction of holdings from free text (`extract_holdings_from_chat`, `ChatExtractionResult`, `TOOL_SCHEMA`). |
| `listing_import.py` | Parse Zillow `homedetails` URLs → `ParsedListing` (zpid, address hint, state, zip). No scraping. |
| `property_recommender.py` | Deterministic property ranking/filtering for onboarding. |

### Platform / infrastructure
| Module | Responsibility |
|---|---|
| `event_store.py` | `EventStore.append` — **the only `domain_events` writer**; sequence tracking, correlation id. |
| `market_state.py` | `build_snapshot(db, property_id)` — **only async entry point** that pulls `MarketSignal` rows → `MarketContextSnapshot`. Neighborhood signals resolved by `neighborhood_id` then `zip_code`; property-level signals win. |
| `signal_writer.py` | `upsert_signal` — **idempotent per calendar day** writer for `market_signals` ((signal_type, subject_type, subject_id) same-day → update in place; new day → insert). |
| `market_data.py` / `market_data_provider.py` | `MarketDataService` + Protocol/Mock/Real provider (`get_local_stats`, `get_active_listings`, `get_comps`). |
| `maps.py` / `geocache.py` | TomTom geocoding + POI; geohash-keyed Redis cache (24h TTL). |
| `redis.py` / `pubsub.py` / `job_queue.py` | Redis pool; `EventBus` (publish/subscribe, `publish_strategy_step`); Redis-Streams job queue (`jobs:simulations`). |
| `metrics.py` | In-memory Prometheus-style counters/histograms/gauges + `Timer`. |
| `logging.py` | structlog JSON setup, correlation-id bound. |
| `user_resolve.py` | `resolve_user_profile` — Supabase id → internal UserProfile (by id → supabase_id → email → auto-create). |
| `address_jp.py` | Offline Tokyo-23-ward address normalization (`NormalizedAddress`, `OfflineTokyoNormalizer`). |
| `money_jp.py` | `MoneyJPY` value object — **integer yen, no floats** (`as_man`/`as_oku`/`format_ja`). |

---

## 8. Layered Domain Runtime (`domain/`)

A seven-stage, **pure-Python / deterministic / lenient** pipeline. No DB, Redis, or
Claude. Builders return frozen dataclasses; missing data → `None`/warn, never raises.

| Stage | Module | Primary types |
|---|---|---|
| Event taxonomy | `events.py` | `EventNamespace` (MARKET/ACTOR/REACTION/DECISION/OUTCOME), `canonical_event()`, `is_known_event()`, frozen event registries |
| Market | `market/` | `MarketContextSnapshot` (transit/school/safety scores, median_rent, median_sale_price, inventory_pressure, hazard_flags, zoning), `MarketShock` |
| Actor / cohort | `actors/profiles.py` | `ActorType` (BUYER…INVESTOR…HOUSEHOLD…UNKNOWN), `ActorSignalState` (8 signed signals: affordability_pressure, trust_in_trajectory, perceived_safety, social_proof, displacement_concern, investor_optimism, willingness_to_transact, resistance_to_development), `CohortSignalState`, `infer_actor_type()`, `user_profile_signals()`, `cohort_signals()` |
| Reaction | `reactions/` | `ReactionVector` (8 vars, range [-1,1], frozen), `ReactionEvent`, `ReactionEngine` (stateful fold; `apply`, `convergence()`, `divergence_score()`), `extract_narratives()` (→ `NarrativeCluster`), `vector_distance()` (Euclidean), `derive.py` (actor/market signals → reaction events → vector) |
| Decision | `decisions/` | `DecisionContext`, `DecisionRecommendation`, `DecisionPolicy` Protocol, `DecisionRuntime` (aggregates policies, sorts by score). Policies: `ListHoldPolicy`, `LeasePolicy`, `ChurnPolicy`, `DevResistancePolicy`, `NegotiationPolicy`; `default_policies()`. **`negotiation.py` = dormant state machine** (10 states, 9 actions, transition table) with no product consumer. |
| Outcome | `outcomes/` | `MarketOutcomeSnapshot`, `build_outcome_snapshot()`, `project_price_movement/time_on_market/offer_behavior/concession_rate/permit_friction/neighborhood_sentiment()` |
| Report / replay | `reports/` | `UnderwritingReport`, `PolicyRiskBrief`, `NegotiationBriefing`, `ReplayFrame`, `ReplayNarrative`; `build_*` builders; `replay_reactions()` re-folds an event stream capturing per-step sentiment |

**Live consumers:** `services/holding_decision.py` → `api/decisions.py` use the decision
runtime. `services/market_state.py` produces the `MarketContextSnapshot`.

---

## 9. Intelligence — Financial Engines (`intelligence/`)

Pure financial math, separate from the domain runtime.

### `underwriting.py` — single-property DCF
- **Inputs:** purchase_price, down_payment, loan_rate, loan_term_years, monthly_rent,
  vacancy_rate, monthly_opex, property_tax_annual, insurance_annual, closing_costs,
  rent_growth, expense_growth, appreciation, exit_cap_rate, selling_costs_pct.
- **Outputs:** monthly_piti, annual_debt_service, effective_gross_income, annual_noi,
  cap_rate, cash_on_cash, dscr, breakeven_occupancy, initial_equity, irr_5yr, irr_10yr.
- **Formulas:**
  - Mortgage payment = `P · r(1+r)ⁿ / ((1+r)ⁿ − 1)`, r = annual_rate/12, n = term·12.
  - **Cap rate** = annual NOI / purchase price.
  - **Cash-on-Cash** = annual cash flow / initial equity.
  - **DSCR** = annual NOI / annual debt service.
  - **Breakeven occupancy** = (OpEx + debt service) / gross rent.
  - **NOI** = EGI − OpEx, EGI = gross rent · (1 − vacancy).
  - **IRR** via bisection over `[-0.99, 10.0]` on the projected cash-flow series (sale at
    exit cap rate in the terminal year).

### `stress_test.py` — Monte-Carlo
- `monte_carlo_stress_test(base, config)` runs N iterations (default 5000 in the engine;
  `MONTE_CARLO_SCENARIOS` config default 300), sampling **5 sliders** uniformly —
  vacancy_rate, rent_growth, expense_growth, loan_rate, exit_cap_rate.
- Reports p10/p50/p90 for cap_rate/CoC/DSCR/IRR, probability of negative cash flow,
  probability DSCR < 1, and a **tornado decomposition** (per-variable CoC swing with
  others held at midpoint).

### `tax_basic.py` — US tax
- `RESIDENTIAL_USEFUL_LIFE_YEARS = 27.5`, long-term cap-gains 0.15 / short-term 0.32.
- `annual_depreciation` = building_value / useful_life (land not depreciable);
  `capital_gains_tax`; `after_tax_sale_proceeds`.

### `depreciation_jp.py` — Japan statutory depreciation (減価償却) + tax shield
- Statutory life (法定耐用年数): WOOD 22, LIGHT_STEEL 27, STEEL 34, RC 47, SRC 47.
- **Used-asset simplified rule (簡便法):** if age ≥ life → residual = life·0.20; else
  residual = (life − age) + age·0.20; floored at 2 years.
- `project_depreciation(...)` → `DepreciationSchedule` of yearly depreciation, tax shield
  (= depreciation · marginal_tax_rate), cumulative shield. **Drives the JP "aparuto tax
  shield" investment thesis.** Consumed by `strategy_runner`.

### `financial_models.py` — **LEGACY, unreferenced** (candidate for removal).

---

## 10. Market-Signal Pipeline & Providers

Real-world signals are ingested, written via the idempotent `signal_writer`, and read
back through `market_state.build_snapshot` into a `MarketContextSnapshot` that the
underwriting/decision surface consumes.

### Provider Protocol (`services/signal_providers/base.py`)
- `ExternalSignal` (frozen DTO): signal_type, subject_type, subject_id, observed_at,
  value, payload.
- `MarketSignalProvider` Protocol: `name`, `async fetch(**kwargs) → Sequence[ExternalSignal]`.
- `registry.py`: `get_provider(name)` factory.

### Providers
| Provider | Source | Signal(s) | Needs |
|---|---|---|---|
| `mock` | Deterministic fixtures (Chicago zips) | various | none (no network) |
| `chicago_crime` | Chicago Data Portal (Socrata `ijzp-q8t2`) | `safety_score` (0–10) | optional app_token |
| `hud_fmr` | HUD User API | `median_rent` (2BR headline + breakdown) | `HUD_FMR_API_TOKEN` |
| `fred` | FRED (`MORTGAGE30US`) | `mortgage_rate_30yr` | `FRED_API_KEY` |
| `fema_nfhl` | FEMA National Flood Hazard Layer | `hazard` (flood zone, per property) | none |
| `census_acs` | US Census ACS 5-year | `median_rent`, `median_home_value` (per zip) | `CENSUS_API_KEY` |

**Adding a provider ≈ 50 lines:** implement the Protocol, register in
`registry.py::_FACTORIES`, mock HTTP with `httpx.MockTransport`.

### Japan providers (`services/providers_jp/`) — **fixture-only mocks today**
| File | Source |
|---|---|
| `estat.py` | e-Stat statistics (population by chome) |
| `kokudo_suuchi.py` | 国土数値情報 (MLIT) hazard/zoning GeoJSON |
| `reinfolib.py` | MLIT 不動産情報ライブラリ transaction data |
| `reins.py` | REINS (MLS-equivalent) listings |

### Signal CLIs (`scripts/`)
- `backfill_market_signals.py` — derive `median_sale_price` + `inventory_pressure` per
  zip and `hazard` per property from the in-DB `properties` table.
- `fetch_external_signals.py --source <name>` — run one provider, upsert via shared writer
  (`--list` shows registered providers).

---

## 11. Claude / AI Usage

Claude is used for **structured intelligence**, not conversation. Three touchpoints:

1. **Listing-analysis council** (`agent/analyst_council.py` + `analyst_personas.py`,
   `POST /api/listings/{id}/analyze`):
   - Serializes a property to JSON, runs **4 personas in parallel** (`asyncio.gather`),
     one **Claude (Haiku)** call each, then a weighted score blend
     (risk 0.40, location 0.30, vacancy 0.20, depreciation 0.10) → `ListingAnalysis`
     (verdicts + overall_score 0–100 + summary). Resilient: a malformed/failed persona
     returns a verdict with an error string without breaking the council.
   - Personas: **リスク発掘 (RISK_FINDER)** — 旧耐震 / 再建築不可 / hazard / 借地権 /
     depreciation runway; **立地優位性 (LOCATION_ADVANTAGE)**; **減価償却戦略
     (DEPRECIATION_STRATEGIST)** — interprets the deterministic JP depreciation schedule;
     **空室・需要 (VACANCY_DEMAND)** — occupancy forecast + rent realism + demand signal.
2. **Portfolio chat import** (`services/portfolio_chat_extractor.py`,
   `POST /api/portfolio/import/chat`): Claude tool-use extracts structured holdings from
   free text; user confirms before persistence.
3. **Strategy profile extraction** (`services/strategy_profile.py`): currently a
   **heuristic** (no Claude call), but designed LLM-pluggable.

Configured via `ANTHROPIC_API_KEY`. Default to the latest Claude models when extending.

---

## 12. Frontend (`frontend/src/`)

React 18 + TS + Vite SPA. Lazy-loaded pages; Supabase auth; typed API client injecting the
Bearer token.

### Routing (`App.tsx`)
| Route | Page |
|---|---|
| `/signin` | SignInPage (Supabase auth) |
| `/` | HomeGate (redirects by onboarding state) |
| `/onboard` | OnboardingWizard |
| `/portfolio` | **PortfolioPage** (auth-guarded) — the product center |
| `/profile/:id?` | UserProfilePage (auth-guarded) |
| `/simulate/:runId` · `/simulate/:runId/report` | SimulatePage / SimulateReportPage |
| (Dashboard) | DashboardPage — holdings map (MapLibre + supercluster) + recommendations |

### `PortfolioPage.tsx` — 6 tabs (operate on the selected portfolio's real holdings)
1. **Analysis** (default) — `GET /portfolio/{id}/summary` → `PortfolioSummaryReport`:
   per-holding cap rate / DSCR / CoC / recommendation + attention list + aggregates.
2. **Holdings** — add/edit/delete holdings; CSV import panel.
3. **Underwrite** — single-property DCF form → `POST /underwrite`.
4. **Stress Test** — 5-slider Monte-Carlo → `POST /underwrite/stress-test`.
5. **Decisions** — per-holding → `GET /decisions/holding/{id}` (HOLD/RAISE_RENT/REFI/
   SELL/IMPROVE + rationale + score).
6. **Simulation** — free text → `POST /strategy/extract` → review `StrategyProfile` →
   `POST /strategy/run` → poll `…/status` then `…/result` → `SimulationReport` +
   `UnifiedReport`.

### Auth & utils
- `auth/AuthProvider.tsx` + `hooks/useAuth.ts` — Supabase session context; `RequireAuth`
  guards sensitive routes.
- `utils/api.ts` — typed fetch wrapper; injects Supabase Bearer token; namespaced clients
  (`properties`, `users`, `portfolio`, `underwrite`, `decisions`, `strategy`,
  `onboarding`, `investorProfile`, `listing`, `recommendations`, `system`).
- `config/runtime.ts` — reads public runtime config (`/api/config/public`).
- `hooks/usePortfolioMode.ts` — localStorage individual/institutional toggle.

---

## 13. Configuration (`config.py`, pydantic-settings ← `.env`)

| Variable | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | "" | Claude (listing analysis + chat import) |
| `TOMTOM_API_KEY` / `ZILLOW_API_KEY` / `ATTOM_API_KEY` | "" | maps / listing data |
| `DATABASE_URL` | `postgresql+asyncpg://dev:dev@localhost:5432/realestate` | |
| `REDIS_URL` | `redis://localhost:6379/0` | pub/sub, cache, job queue |
| `SUPABASE_URL` / `SUPABASE_JWT_ISSUER` / `SUPABASE_JWKS_URL` | "" | auth; **empty ⇒ auth passthrough** |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | expected `aud` |
| `SUPABASE_JWT_SECRET` | "" | legacy HS256 only |
| `SUPABASE_SERVICE_ROLE_KEY` | "" | server-only admin (dev-user script) |
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` | "" | exposed to SPA |
| `PUBLIC_API_BASE_URL` (`VITE_API_BASE_URL`) | `/api` | |
| `PUBLIC_WS_BASE_URL` (`VITE_WS_URL`) | `/ws` | |
| `PUBLIC_MAP_STYLE_URL` | (map style) | MapLibre style |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | |
| `MARKET_DATA_PROVIDER` | `mock` | mock or real |
| `MONTE_CARLO_SCENARIOS` | `300` | stress-test iterations |
| `JURISDICTION` | `us` | `us` or `jp` |
| `DEFAULT_PREFECTURE_CODE` | `13` | 東京都 |
| `REINS_MODE` / `REINFOLIB_MODE` | `mock` | JP data sources |
| `REINFOLIB_API_KEY` / `ESTAT_APP_ID` / `RESAS_API_KEY` / `GOOGLE_MAPS_API_KEY` | "" | JP provider keys |
| `EMBEDDER_MODE` / `EMBEDDING_DIM` / `VOYAGE_API_KEY` / `COHERE_API_KEY` | `hash` / 64 / "" | embeddings |
| `ENVIRONMENT` / `LOG_LEVEL` | `development` / `INFO` | |
| **Legacy (no consumers)** | | `MIROFISH_*`, `MAX_DEAL_VALUE_AUTO`, `MIN_OFFER_PERCENT`, `MAX_COUNTER_ROUNDS`, `MAX_SIMULATION_ROUNDS`, `MAX_BATCH_SCENARIOS` |

---

## 14. Database Migrations (`alembic/versions/`)

Async Alembic; **head = `f9a1b2c3d4e5`**. 14 migrations chronologically:
initial schema + domain_events → supabase_user_id → JP property/tier columns →
investor_profile → market_signals → (negotiation/social-sim/market-sim/household tables)
→ investor_portfolio tables → offer-ledger normalization → merge → **`f9a1b2c3d4e5`
(drop negotiation/social/market-sim)**.

The head migration **dropped 15 tables** (one-way, CASCADE + IF EXISTS):
- Negotiation: negotiations, offers, agent_decisions, agent_memory, simulation_results.
- Social sim: social_simulation_actions/runs, household_social_edges, household_profiles.
- Market sim: market_simulation_decisions/property_states/investors/runs.
- MiroFish: mirofish_reports, mirofish_seeds.

This is the migration that enacted the pivot to JP investor analytics.

---

## 15. Testing

- **~51 pytest files** in `tests/`, pytest-asyncio (`asyncio_mode=auto`).
- **In-memory SQLite** (`:memory:` via aiosqlite, JSONB→JSON patched); **fakeredis** for
  Redis; **no external services / no Docker** required. External HTTP mocked with
  `httpx.MockTransport`.
- `conftest.py` fixtures: `db_engine`, `db` (rollback-per-test AsyncSession), mock redis,
  settings override.
- Coverage spans: API endpoints (`test_api_*`), domain structure/events, signal providers
  (US + JP), underwriting/tax/depreciation, stress test, portfolio summary & holding
  decision, strategy runner/profile/events/steps, market state, auth middleware,
  correlation id, pub/sub, JP helpers (money/address), seeds.
- **Project rule:** run `pytest tests/ -v` before committing; target 80%+ coverage; TDD
  (write failing test first) for new features.

---

## 16. Critical Patterns & Conventions (follow these)

1. **Event sourcing** — state-changing flows append to `domain_events` with a correlation
   id, via `EventStore.append` (the only writer). Strategy runs are audited this way
   (`strategy.run_started` / `…_completed` / `…_failed`).
2. **Async-first** — all DB/Redis/HTTP/Claude calls are async; use `asyncio.Semaphore`/
   locks for concurrency.
3. **Provider pattern** — market data, maps, and signal sources are Protocol-based with
   mock + real implementations; always support both modes.
4. **Resilient external calls** — `tenacity` retry/backoff; inject `httpx.AsyncClient` so
   tests use `MockTransport`.
5. **Correlation IDs everywhere** — thread through logs, events, decisions; background
   tasks capture it at request time (contextvar does not propagate).
6. **`domain/` is pure** — no I/O, deterministic, frozen dataclasses.
7. **Lenient projections** — warn + default on missing data; never raise (except the
   dormant negotiation state machine).
8. **Market-signal writes go through `signal_writer.upsert_signal`** (idempotent per day).
9. **Reuse the strategy pipeline** — build on `portfolio_summary` → `strategy_runner` →
   `unified_report`; don't re-derive analysis/simulation/reconciliation logic.
10. **Immutability & small files** — new copies over mutation; 200–400 line files;
    structlog over `print`; type hints throughout; UUID PKs; JSONB for flexible payloads.

---

## 17. Quick Commands

```bash
# Infrastructure
docker compose -f ~/docker-shared-services.yml up -d postgres redis
bash scripts/init-shared-db.sh

# Backend
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_properties.py          # or seed_tokyo / seed_kaggle_usa / seed_from_csv
python scripts/seed_dev_portfolio.py       # demo investor portfolio + holdings
python scripts/create_dev_user.py          # dev auth account (needs Supabase keys)
uvicorn main:app --reload                  # http://localhost:8000

# Market signals
python scripts/backfill_market_signals.py
python scripts/fetch_external_signals.py --list
python scripts/fetch_external_signals.py --source mock

# Frontend
cd frontend && npm install && npm run dev  # http://localhost:5173
npm run test        # Vitest
npm run test:e2e    # Playwright

# Tests (backend)
pytest tests/ -v
pytest tests/ --cov=. --cov-report=term-missing
```

---

## 18. Glossary (Japan domain terms)

| Term | Meaning |
|---|---|
| 売買価格 (baibai_kakaku) | Sale/purchase price |
| 管理費 (kanrihi) | Monthly building management fee |
| 修繕積立金 (shuuzen tsumitatekin) | Reserve fund for major repairs |
| 用途地域 (youto_chiiki) | Zoning / land-use district |
| 建蔽率 (kenpei_ritsu) | Building coverage ratio |
| 容積率 (youseki_ritsu) | Floor-area ratio |
| 面積 (menseki) | Area (m²) |
| 再建築不可 / 再建築可否 | Cannot / can be rebuilt (legal buildability) |
| 旧耐震 / 新耐震 (kyu/shin taishin) | Pre-1981-06 / post seismic code |
| 法定耐用年数 | Statutory useful life (depreciation) |
| 簡便法 | Simplified used-asset depreciation rule |
| アパート (aparuto) | Low-rise wood/light-steel apartment building |
| マンション (mansion) | Mid/high-rise RC/SRC condo building |
| 万 / 億 (man / oku) | 10,000 / 100,000,000 (yen magnitudes) |
| REINS | Real Estate Information Network System (JP MLS) |
| 国土数値情報 | MLIT National Land Numerical Information (hazard/zoning) |
| e-Stat / RESAS | JP government statistics portals |

---

*Generated as a comprehensive, self-contained project specification. For AI-coding-agent
operational guidance and the most authoritative architecture notes, see `CLAUDE.md`.*
