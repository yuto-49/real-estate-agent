# Simulation & Intelligence Report Architecture

This document describes the intelligence report pipeline (MiroFish analysis) and the negotiation simulation engine, including how they integrate.

---

## 1. Intelligence Report Structure (MiroFish)

### 1.1 MiroFishReportData Fields

The `MiroFishReportData` dataclass (`intelligence/mirofish_client.py`) holds the full analysis:

| Field | Type | Description |
|---|---|---|
| `market_outlook` | dict | Market trend, confidence score, appreciation projections, health score |
| `timing_recommendation` | dict | Buy/wait recommendation with reasoning |
| `strategy_comparison` | list[dict] | Aggressive/Balanced/Conservative strategies with offer %, success probability |
| `risk_assessment` | list[dict] | Risk factors with severity and probability |
| `property_recommendations` | list[dict] | Ranked property suggestions |
| `decision_anchors` | dict | `max_recommended_price`, `walk_away_price`, price boundaries |
| `financial_analysis` | dict | Mortgage payments, amortization, affordability metrics, cash flow |
| `monte_carlo_results` | dict | `probability_of_loss`, IRR distribution (p10/p25/p50/p75/p90), `mean_irr` |
| `cash_flow_projections` | dict | Monthly/annual income vs expense breakdown |
| `rent_vs_buy_analysis` | dict | Break-even timeline, comparative total cost |
| `tax_benefit_estimation` | dict | Deductions, effective savings |
| `portfolio_metrics` | dict | Diversification score, total exposure |
| `comparable_sales_analysis` | dict | `median_price_per_sqft`, `value_indicator`, comparable sales list |
| `neighborhood_scoring` | dict | `overall_score`, sub-scores (schools, transit, safety, etc.) |
| `raw_json` | dict | Full unprocessed report data |

### 1.2 Report Generation Pipeline

```
User Profile + Market Data + Listings
        │
        ▼
  SeedAssemblyService (intelligence/seed_assembly.py)
  ├─ Section 1: Buyer Profile
  ├─ Section 2: Target Market Analysis
  ├─ Section 3: Property Shortlist
  ├─ Section 4: Financial Parameters
  └─ Section 5: Decision Framework
        │
        ▼
  MiroFish Client (intelligence/mirofish_client.py)
  ├─ Phase 1: Base Financials (mortgage, affordability, cash flow)
  ├─ Phase 2: Monte Carlo Simulation (10,000 runs → IRR distribution, loss probability)
  ├─ Phase 3: Comparative Analysis (comps, neighborhood, rent-vs-buy)
  └─ Phase 4: Synthesis (strategies, decision anchors, timing, risk assessment)
        │
        ▼
  MiroFishReportData → stored as JSONB in mirofish_reports table
```

### 1.3 Financial Models (`intelligence/financial_models.py`)

| Class | Purpose |
|---|---|
| `MortgageCalculator` | Monthly payment (P&I), amortization schedule |
| `CashFlowModel` | Net operating income, cap rate, cash-on-cash return |
| `InvestmentMetrics` | IRR, NPV, equity buildup |
| `MonteCarloEngine` | 10,000-run simulation varying appreciation, vacancy, rates → IRR distribution |
| `TaxEstimator` | Mortgage interest deduction, property tax deduction, depreciation |
| `PortfolioMetrics` | Diversification score, total real estate exposure |

---

## 2. Negotiation Simulation Structure

### 2.1 Core Components

```
NegotiationSimulator (services/negotiation_simulator.py)
    │
    ├── BuyerAgent (agent/buyer_agent.py)
    │   └── Tools: search_properties, analyze_neighborhood, place_offer,
    │             accept_offer, get_comps, counter_offer,
    │             get_intelligence_report, get_negotiation_intel
    │
    ├── SellerAgent (agent/seller_agent.py)
    │   └── Tools: list_property, set_asking_price, evaluate_offer,
    │             counter_offer, get_comps, analyze_neighborhood,
    │             get_intelligence_report, get_negotiation_intel
    │
    └── BrokerAgent (agent/broker_agent.py)
        └── Tools: mediate_negotiation, market_analysis, generate_contract,
                  schedule_inspection, get_comps, analyze_neighborhood,
                  get_intelligence_report, get_negotiation_intel
```

### 2.2 Simulation Flow

```
1. Config received (property_id, asking_price, initial_offer, strategy, etc.)
2. If report_data provided:
   a. derive_config_from_report() → auto-set strategy, initial_offer, buyer_maximum
   b. _build_intelligence_briefings() → create role-specific text summaries
3. SimulationState initialized (tracks prices, offers, price_path)
4. Simulation tools created (in-memory mocks replacing DB-backed tools)
5. Round loop (up to max_rounds):
   a. Build context (round info, prices, intelligence briefing)
   b. Buyer agent turn → Claude API call → tool use → counter/accept
   c. Seller agent turn → Claude API call → tool use → counter/accept
   d. If spread < 5% after round 5 → broker mediation round
   e. Check for acceptance → break if deal reached
6. Result: outcome, final_price, transcript, price_path, summary
7. Persist to simulation_results table (if buyer_user_id provided)
```

### 2.3 SimulationState (`agent/simulation_tools.py`)

Tracks all in-memory state for one simulation run:

| Field | Type | Purpose |
|---|---|---|
| `negotiation_id` | str | Unique negotiation identifier |
| `property_id` | str | Target property |
| `asking_price` | float | Seller's asking price |
| `buyer_maximum` | float | Buyer's ceiling (hidden from seller) |
| `seller_minimum` | float | Seller's floor (hidden from buyer) |
| `current_round` | int | Current negotiation round |
| `buyer_latest_price` | float | Buyer's most recent offer |
| `seller_latest_price` | float | Seller's most recent counter |
| `offers` | list[dict] | Full offer/counter history |
| `status` | str | active / accepted / rejected |
| `price_path` | list[dict] | `[{round, role, price}]` for visualization |

### 2.4 Simulation Tools (In-Memory Mocks)

During simulation, real DB-backed tools are replaced with in-memory handlers:

| Tool | Behavior |
|---|---|
| `sim_place_offer` | Records offer in state, updates buyer_latest_price |
| `sim_counter_offer` | Records counter, updates buyer/seller latest price, calculates spread |
| `sim_accept_offer` | Marks deal accepted, records final price |
| `sim_evaluate_offer` | Returns spread analysis and recommendation (accept/counter_split/counter_higher) |
| `sim_mediate_negotiation` | Returns both positions, spread, midpoint, and recommendation |
| `sim_get_intelligence_report` | Returns report data from kwargs |
| `sim_get_negotiation_intel` | Returns curated report aspect (pricing/risk/strategy/market/comps) |

### 2.5 Tool Access Control (`agent/tool_acl.py`)

Role-based ACL filters which tools each agent can call:

| Role | Allowed Tools |
|---|---|
| **BUYER** | search_properties, analyze_neighborhood, place_offer, accept_offer, get_comps, counter_offer, get_intelligence_report, get_negotiation_intel |
| **SELLER** | list_property, set_asking_price, evaluate_offer, counter_offer, get_comps, analyze_neighborhood, get_intelligence_report, get_negotiation_intel |
| **BROKER** | mediate_negotiation, market_analysis, generate_contract, schedule_inspection, get_comps, analyze_neighborhood, get_intelligence_report, get_negotiation_intel |

### 2.6 Persistence (`db/models.py` → `SimulationResult`)

Completed simulations are persisted to `simulation_results` table:

| Column | Type | Description |
|---|---|---|
| `id` | String (PK) | UUID |
| `user_id` | String (FK → user_profiles) | Who ran the simulation |
| `property_id` | String | Target property |
| `batch_id` | String (nullable) | Groups scenarios in a batch run |
| `scenario_name` | String (nullable) | e.g. "aggressive", "conservative" |
| `outcome` | String | accepted / rejected / max_rounds / broker_stopped / failed |
| `final_price` | Float (nullable) | Agreed price if accepted |
| `asking_price` | Float | Original asking price |
| `initial_offer` | Float | Starting offer |
| `rounds_completed` | Integer | How many rounds ran |
| `max_rounds` | Integer | Configured maximum |
| `strategy` | String | aggressive / balanced / conservative |
| `summary` | JSONB | Buyer/seller final positions, spread data |
| `price_path` | JSONB | `[{round, role, price}]` array for charts |
| `created_at` | DateTime | Timestamp |

---

## 3. Intelligence Report → Simulation Bridge

### 3.1 `derive_config_from_report(report_data, asking_price)`

Translates financial analysis into simulation config:

| Report Field | Derived Config | Logic |
|---|---|---|
| `decision_anchors.max_recommended_price` | `buyer_maximum` | Direct mapping |
| `decision_anchors.walk_away_price` | `buyer_walk_away` | Direct mapping |
| `market_outlook.trend` + `monte_carlo.probability_of_loss` | `strategy` | High risk (prob_loss > 0.3 or health < 60) → conservative; strong market + low risk → aggressive; else balanced |
| `strategy_comparison[chosen].recommended_offer_pct` | `initial_offer` | `asking_price × (offer_pct / 100)` |
| `comparable_sales_analysis.value_indicator` | `initial_offer` (fallback) | above_market → 90%; below_market → 97% |
| `timing_recommendation.action` | `scenario_constraints.buyer_urgency` | buy_now → high; wait_3_months → low |
| `risk_assessment` (high severity + prob > 0.3) | `max_rounds` | Capped at 8 to cut losses early |

### 3.2 Intelligence Briefings (Injected into Agent Context)

Instead of raw JSON, agents receive **distilled natural-language briefings**:

- **Buyer briefing**: Market trend, comps position ($/sqft), decision anchors, strategy recommendation with success probability, Monte Carlo risk metrics, cash flow, timing action, and negotiation directives
- **Seller briefing**: Market trend, comps position, neighborhood scores (top features), negotiation directives based on value indicator and market trend
- **Broker briefing**: Both positions, ZOPA estimate, spread analysis, market context, recommendations for mediation

### 3.3 On-Demand Intelligence (`get_negotiation_intel` Tool)

Agents can request specific aspects mid-negotiation:

| Aspect | Returns |
|---|---|
| `pricing` | max_recommended_price, walk_away_price, value_indicator, price/sqft, current spread |
| `risk` | probability_of_loss, IRR range, key risk factors (top 4) |
| `strategy` | All strategy options with offer %, success probability, risk level |
| `market` | Trend, confidence, appreciation %, health score, timing action |
| `comps` | Value indicator, median $/sqft, recent sales (top 5) |
| `all` | Everything above combined |

---

## 4. API Endpoints

### Simulation API (`/api/simulation/`)

| Method | Path | Description |
|---|---|---|
| POST | `/start` | Start simulation with manual config (optionally seeded by report_id) |
| POST | `/start-from-report` | Start simulation fully seeded by a MiroFish report |
| GET | `/status/{sim_id}` | Poll running simulation status |
| GET | `/result/{sim_id}` | Get completed simulation results |
| GET | `/list` | List in-memory simulations (filtered by property_id, status) |
| GET | `/results` | List persisted simulation results from DB (filtered by user_id) |
| GET | `/results/{result_id}` | Get single persisted result |

### Batch Simulation API (`/api/batch-simulation/`)

| Method | Path | Description |
|---|---|---|
| POST | `/start` | Start batch of scenario variants (aggressive, balanced, conservative, etc.) |
| GET | `/status/{batch_id}` | Batch progress |
| GET | `/results/{batch_id}` | All scenario outcomes |

---

## 5. Scenario Variants (`services/scenario_variants.py`)

Six pre-defined scenarios for batch runs:

| Scenario | Strategy | Constraints |
|---|---|---|
| Aggressive Buyer | aggressive | buyer_urgency: low, market_knowledge: high |
| Conservative Buyer | conservative | buyer_urgency: low, risk_tolerance: low |
| Balanced Approach | balanced | standard constraints |
| Multiple Offers | aggressive | competing_offers: 2, time_pressure: high |
| Slow Market | balanced | market_condition: slow, days_on_market: 90 |
| Cash Buyer | aggressive | financing: cash, closing_speed: fast |
