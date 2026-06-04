# Architecture — Tokyo Workforce-Housing Investor Analytics

## 1. System Purpose

This platform helps Tokyo small-to-mid-scale investors decide **which income
property to buy and whether the thesis survives a 10-year projection**. It
does not run transaction chat, NIMBY sentiment surveys, or synthetic market
universes. Every component points at one question:

> *Given this investor's cash + strategy, which Tokyo listings should they
> buy, and does the projected cash flow + depreciation tax shield survive
> rate, occupancy, and rent shocks?*

The platform models three Tokyo workforce-housing asset tiers explicitly:

| Tier | Unit | Investor strategy | What the math turns on |
|---|---|---|---|
| **ワンルーム** (One-Room Mansion) | 20–30 m² studio in a large RC/SRC complex | Station-proximity yield, near-zero vacancy | 駅徒歩, 管理費/修繕積立金 drag, GPR yield |
| **アパート** (Aparuto) | 4–12 unit 木造 / 軽量鉄骨 building | High net yield via accelerated 減価償却 tax shield | Construction type → 法定耐用年数, age, building/land basis split |
| **ファミリー** (Family Mansion) | 55–80 m² 2LDK/3LDK in 江東/江戸川/墨田/葛飾 | Urban-migration appreciation + stable family tenant | Commute to 丸の内/日本橋, 区 demographics, school catchment |

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT (React 18 + Vite)                   │
│  Onboarding wizard · Portfolio · Listing review · Unified report    │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────▼────────────────────────────────────────┐
│                       API GATEWAY (FastAPI)                         │
│  Middleware: Correlation ID · Supabase JWT · Rate limit · CORS      │
│                                                                     │
│  Routers:                                                           │
│    /api/properties      /api/search          /api/users             │
│    /api/portfolio       /api/investor-profile                       │
│    /api/onboarding      /api/strategy         /api/decisions        │
│    /api/underwrite      /api/listing                                │
│    /api/listings/{id}/analyze  ← persona analyst council            │
│    /api/config/public                                               │
└──────┬───────────────────┬───────────────────┬──────────────────────┘
       │                   │                   │
┌──────▼──────────┐ ┌──────▼──────────┐ ┌──────▼──────────────────────┐
│ Persona Analyst │ │ Lifetime Sim    │ │ Recommender                 │
│ Council         │ │ (deterministic) │ │ (asset-tier aware)          │
│                 │ │                 │ │                             │
│ Risk Finder     │ │ DCF +           │ │ Tier filter (one-room /     │
│ Location Adv.   │ │ Monte Carlo +   │ │  aparuto / family) →        │
│ Depreciation    │ │ depreciation    │ │ scored ranking by           │
│ Vacancy/Demand  │ │ tax shield +    │ │ proximity, yield, hazard    │
│ (4× Haiku       │ │ stress paths    │ │                             │
│  parallel)      │ │                 │ │                             │
└──────┬──────────┘ └──────┬──────────┘ └──────┬──────────────────────┘
       │                   │                   │
┌──────▼───────────────────▼───────────────────▼──────────────────────┐
│                    DATA & MESSAGING LAYER                           │
│                                                                     │
│  ┌──────────────────────────┐    ┌────────────────────────────────┐ │
│  │      PostgreSQL 16       │    │            Redis 7             │ │
│  │                          │    │                                │ │
│  │  user_profiles           │    │  Geocache                      │ │
│  │  properties (+ JP cols)  │    │  Rate-limit counters           │ │
│  │  investor_profiles       │    │  Session cache                 │ │
│  │  investor_portfolios     │    │                                │ │
│  │  portfolio_holdings      │    │                                │ │
│  │  holding_financials      │    │                                │ │
│  │  underwriting_scenarios  │    │                                │ │
│  │  market_signals          │    │                                │ │
│  │  domain_events (audit)   │    │                                │ │
│  └──────────────────────────┘    └────────────────────────────────┘ │
└──────┬──────────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────────┐
│                       EXTERNAL SERVICES                             │
│                                                                     │
│  Claude API (Anthropic)    Maps (TomTom / NAVITIME)                 │
│  - Persona analysts        - Geocoding                              │
│                            - Walk-minute calculation                │
│                                                                     │
│  JP signal providers (in services/signal_providers + providers_jp): │
│  - e-Stat (国勢調査 demographics)                                    │
│  - REINS / Reinfolib (transaction prices)                           │
│  - 国土数値情報 (zoning, hazard layers)                              │
│                                                                     │
│  Supabase Auth (JWT)                                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Workflow

### 3.1 Onboarding → Investor Profile

1. User signs in via Supabase.
2. Onboarding wizard captures: budget, target asset tier, ward focus, target
   cap rate / cash-on-cash, hold horizon, marginal income tax bracket.
3. Persisted as `investor_profiles` (one row per user).

### 3.2 Recommendation → Listing Shortlist

1. `services/property_recommender.py` filters listings by `asset_tier`,
   ward, budget, and 駅徒歩 minutes, then ranks by yield + hazard score.
2. Surfaces 5–20 listings on the dashboard.

### 3.3 Listing Review → Analyst Council

For each listing the investor wants to evaluate:

```
POST /api/listings/{id}/analyze
{
  "building_basis_yen": 25000000,
  "building_age_years": 15,
  "marginal_tax_rate": 0.33
}
```

The council runs **four Claude personas in parallel** (`asyncio.gather`),
each on Haiku 4.5:

| Persona | Reads | Emits |
|---|---|---|
| **Risk Finder** | Listing + seismic code + 再建築可否 + hazard flags | `{verdict, score, red_flags[], summary}` |
| **Location Advantage** | Listing + 駅徒歩 + ward demographics + tier fit | `{score, highlights[], tier_fit, summary}` |
| **Depreciation Strategist** | Listing + deterministic depreciation schedule | `{thesis, shield_total_yen, shield_expires_year, summary}` |
| **Vacancy / Demand** | Listing + area signals + assumed rent | `{occupancy_forecast, rent_realism, demand_signal, summary}` |

The depreciation strategist receives a **pre-computed** schedule from
`intelligence/depreciation_jp.py` so it interprets a deterministic table
rather than computing it itself — no math hallucinations.

Verdicts are blended with weights `risk 0.40 / location 0.30 / vacancy 0.20 /
depreciation 0.10` into an `overall_score` (0–100). A persona failure
(network, malformed JSON) isolates without breaking the council.

**Cost per review: ≤4 Claude calls.** This is the entire LLM cost surface.

### 3.4 Portfolio Analysis → Unified Report

Once the investor owns holdings:

1. `services/portfolio_summary.py` produces today's snapshot
   (`PortfolioSummaryReport`) — cap rate, cash flow, attention items.
2. `services/strategy_runner.py::project_simulation` projects each holding
   over the profile's `hold_period_years` (`SimulationReport`). Inputs
   include `assumptions` (rent growth, expense growth, exit cap),
   `policy_config`, and `thesis.market_outlook`.
3. `services/unified_report.py::reconcile_unified_report` answers
   *"does this strategy survive its own projection?"* — flagging holdings
   whose recommendation flips (HOLD → SELL, REFI → HOLD, etc.) and surfacing
   `agreements` and `divergences`.

This pipeline is **pure deterministic math** — no LLM calls. The persona
council operates upstream on individual listings; the unified report
operates downstream on the whole portfolio over time.

---

## 4. Depreciation Engine — the Aparuto Thesis

`intelligence/depreciation_jp.py` implements 法定耐用年数 and 簡便法 from
first principles. The Aparuto pitch in code:

```python
# 15-year-old 木造 building, 25M yen building basis, 33% bracket
schedule = project_depreciation(
    construction=ConstructionType.WOOD,        # 法定耐用年数 22 年
    building_basis_yen=25_000_000,
    building_age_years=15,
    marginal_tax_rate=0.33,
)
# residual_life_years = (22 - 15) + 15 × 0.20 = 10 years
# annual_depreciation_yen ≈ 2.5M
# total tax shield ≈ 8.25M yen over 10 years
# shield_expires_year = 10  ← after this, cash flow flips
```

This module is **pure** — no DB, no Pydantic. Callers (analyst council,
lifetime sim) wrap the dataclass result for their own context.

| Construction | 法定耐用年数 | Aparuto fit |
|---|---|---|
| 木造 (WOOD) | 22 年 | ★★★ — fastest shield expiry, highest annual write-off |
| 軽量鉄骨 (LIGHT_STEEL) | 27 年 | ★★ — moderate shield, longer runway |
| 鉄骨 (STEEL) | 34 年 | ★ |
| 鉄筋コンクリート (RC) | 47 年 | family-mansion stability play, not Aparuto |
| 鉄骨鉄筋コンクリート (SRC) | 47 年 | same as RC |

---

## 5. Audit Trail

Every state change still writes to `domain_events` (append-only, sequenced
per aggregate). The original Fair Housing / LIHTC framing has been retired
— this is now used for:

- **宅建業法 compliance** — proving every recommendation was computed from
  inspected listing data, not opinion.
- **Replay** — reconstructing portfolio state at any point in time.
- **Persona-council audit** — each `analyze` call writes a `ListingAnalysis`
  event with every verdict's payload, so the investor can show their tax
  accountant exactly which inputs drove the depreciation strategist's call.

Future addition: stamp every Claude call with `prompt_version` and
`model_id` on the event payload.

---

## 6. What Was Removed (Pivot Migration `f9a1b2c3d4e5`)

The platform deliberately deleted three feature areas that did not serve
the new target:

| Removed | Replaced by | Why |
|---|---|---|
| Buyer/seller/broker negotiation chat + state machine | (nothing — out of scope) | Tokyo investors transact via 仲介, not chat |
| Household NIMBY social simulator | Vacancy/Demand analyst persona | Investors care about 入居率, not community sentiment |
| Synthetic tick-based market simulator | Real listing recommender | The sim built a parallel universe instead of ranking real listings |
| MiroFish swarm-intelligence projection | Deterministic lifetime sim (`strategy_runner` + `depreciation_jp`) | The remote MiroFish service never shipped; the mock was a stub |
| US signal providers (HUD, FEMA, FRED, Census ACS, Chicago crime) | JP signal providers (e-Stat, REINS, 国土数値情報) | Single-jurisdiction simplification |

Migration `f9a1b2c3d4e5` drops 15 tables. Migration `a1c4e6b8d2f0` adds 9
JP discriminator columns (`asset_tier`, `construction_type`, `seismic_code`,
`re_buildable`, `road_frontage_m`, `ward_code`, `walk_minutes_to_station`,
`assumed_monthly_rent_yen`, `occupancy_rate`).

---

## 7. Source-Tree Map (Post-Pivot)

```
real-estate-agent/
  main.py                       # 11 routers
  config.py
  agent/
    analyst_personas.py         # 4 Haiku personas (risk, location, depreciation, vacancy)
    analyst_council.py          # parallel runner + weighted blender
  api/
    onboarding.py
    investor_profile.py
    portfolio.py
    properties.py               # listing CRUD
    search.py
    listing_analysis.py         # POST /api/listings/{id}/analyze
    underwrite.py               # JP-native scenarios
    strategy.py
    decisions.py
    users.py
    public_config.py
    schemas.py
  db/
    database.py
    models.py                   # 10 tables, no negotiation/social/market-sim
  intelligence/
    depreciation_jp.py          # 法定耐用年数 + 簡便法 + tax shield
    financial_models.py         # DCF + Monte Carlo
    stress_test.py
    underwriting.py
    tax_basic.py
  services/
    property_recommender.py
    portfolio_summary.py
    portfolio_chat_extractor.py
    listing_import.py
    strategy_profile.py
    strategy_runner.py
    unified_report.py
    holding_decision.py
    market_state.py
    market_data.py / market_data_provider.py
    signal_providers/           # FRED/HUD/Census/FEMA/Chicago retained for now;
                                # next sweep replaces with JP-only equivalents
    providers_jp/
      estat.py
      kokudo_suuchi.py
      reinfolib.py
      reins.py
    address_jp.py / money_jp.py
    user_resolve.py             # to be removed once auth becomes Depends-based
    event_store.py
    redis.py / pubsub.py
    maps.py / geocache.py
    metrics.py / logging.py
  middleware/
    correlation.py / auth.py / rate_limit.py
  frontend/                     # React 18 + Vite (parallel sweep pending)
  alembic/
  tests/
```

Roughly **half the surface area** of the pre-pivot system, with every
remaining piece pointed at: *should this investor buy this listing under
this thesis, and does the cash flow + tax shield survive ten years?*
