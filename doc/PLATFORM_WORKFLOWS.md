# Real Estate Agentic Platform — Workflows & Architecture

## Table of Contents

1. [Platform Overview](#platform-overview)
2. [Page Workflows](#page-workflows)
   - [Search Page](#search-page)
   - [Users Page](#users-page)
   - [Report (Intelligence) Page](#report-intelligence-page)
   - [Negotiation Page](#negotiation-page)
   - [Simulation Page](#simulation-page)
   - [System Page](#system-page)
3. [MiroFish Intelligence System](#mirofish-intelligence-system)
   - [Seed Assembly](#seed-assembly)
   - [Tick-Based Phases](#tick-based-phases)
   - [Financial Models](#financial-models)
   - [Report Output Structure](#report-output-structure)
4. [AI Agent System](#ai-agent-system)
   - [Agent Architecture](#agent-architecture)
   - [Buyer Agent](#buyer-agent)
   - [Seller Agent](#seller-agent)
   - [Broker Agent](#broker-agent)
   - [Assistant Agent](#assistant-agent)
   - [Tool ACL (Access Control)](#tool-acl)
   - [Agent Orchestrator](#agent-orchestrator)
5. [Negotiation Simulation Engine](#negotiation-simulation-engine)
6. [Backend API Reference](#backend-api-reference)
7. [Data Flow Diagrams](#data-flow-diagrams)
8. [Database Models](#database-models)
9. [External Integrations](#external-integrations)

---

## Platform Overview

A full-stack real estate transaction platform powered by AI agents (Claude API). The system helps investors make data-driven decisions through:

- **Property Discovery** — Search and filter listings on an interactive map
- **AI-Powered Negotiation** — Buyer, Seller, and Broker agents with role-specific strategies
- **Financial Intelligence** — Deep MiroFish reports with Monte Carlo simulations, mortgage analysis, cash flow projections
- **Automated Simulation** — Multi-round agent-vs-agent negotiation with live transcript
- **Investment Assistant** — Chat-based guidance using reference properties and MiroFish data

**Tech Stack**: React + TypeScript (frontend), FastAPI + SQLAlchemy (backend), Claude Sonnet 4 (AI), PostgreSQL (database), Redis (pub/sub), TomTom Maps (geocoding/POI)

---

## Page Workflows

### Search Page

**File**: `frontend/src/pages/SearchPage.tsx`

**Purpose**: Central hub for property discovery, map-based browsing, and AI-assisted investment analysis.

**Components**:
- Property filter bar (location, price range, property type)
- Interactive MapView (MapLibre) with property markers
- Property cards list with detail overlay
- Collapsible AI Assistant chat panel (sticky sidebar)
- MiroFish Analysis launcher
- Reference property banner

**User Flow**:

```
1. Browse Properties
   User applies filters → GET /api/properties → Map + cards update

2. Select Reference Property
   Click property on map or list → Detail overlay appears
   Click "Find Similar Properties" → Property becomes reference
   → Dark banner shows reference info
   → AI Assistant panel opens automatically
   → Chat pre-fills with: "I've selected [address] as reference.
      Run a MiroFish analysis and find similar properties."

3. Chat with AI Assistant
   User types message → POST /api/agent/message (role=assistant)
   → Agent uses search_properties, analyze_neighborhood, get_intelligence_report tools
   → Response displayed in chat with expandable tool call details

4. Run MiroFish Analysis (standalone)
   Click "Run MiroFish Analysis" button
   → POST /api/reports/generate with current filters as location overrides
   → Poll GET /api/reports/status/{id} every 1.5s
   → When complete, report available in Intelligence page
```

**Key State**:
- `referenceProperty` — Selected property for comparison
- `assistantMessages` — Chat history with AI
- `assistantOpen` — Panel visibility toggle
- `selectedReportId` — Active MiroFish report for agent context

---

### Users Page

**File**: `frontend/src/pages/UsersPage.tsx`

**Purpose**: View investor profiles and generate intelligence reports.

**User Flow**:

```
1. Select user from sidebar list
2. View profile details: role, budget, timeline, risk tolerance, location, preferred types
3. Enter custom question in text area (e.g., "Should I invest in 60601?")
4. Click "Generate Report"
   → POST /api/reports/generate (user_id, question)
   → Redirects to Report page to view progress
```

**Profile Fields**: name, email, role (buyer/seller/both), budget_min/max, life_stage, investment_goals, risk_tolerance, timeline_days, location (zip/lat/lng), search_radius, preferred_types

---

### Report (Intelligence) Page

**File**: `frontend/src/pages/ReportPage.tsx`

**Purpose**: Display MiroFish intelligence reports with detailed financial analysis.

**Two Views**:

1. **Report List** — Select user, filter by status, see all reports
2. **Report Detail** — Full report with workflow progress + financial sections

**Workflow Progress Indicator** (8 steps):

```
Queued (0%)
  → Loading Profile (10%)
  → Fetching Market (25%)
  → Enriching Listings (40%)
  → Assembling Seed (55%)
  → Running Simulation (70%)
  → Parsing Results (85%)
  → Completed (100%)
```

**Report Sections** (rendered with specialized formatters):

| Section | Renderer | Content |
|---------|----------|---------|
| Financial Analysis | Mortgage metrics, cash flow grid | Monthly payment, total interest, equity %, net cash flow |
| Monte Carlo Results | Percentile distribution bars | IRR/NPV at p10/p25/p50/p75/p90, probability of loss |
| Cash Flow Projections | Bear/Base/Bull scenario cards | 5/10/15/30 year projections per scenario |
| Rent vs Buy | Break-even + cost comparison | Break-even months, scenario comparisons |
| Tax Benefits | Savings metrics grid | Mortgage interest deduction, depreciation, annual savings |
| Portfolio Metrics | Metric cards | Sharpe ratio, max drawdown, diversification score |
| Comparable Sales | Subject vs median comparison | Price/sqft, comp property cards |
| Neighborhood Scoring | Category score bars (color-coded) | Schools, transit, dining, parks, overall score |
| Market Outlook | Key-value display | Direction, confidence, factors |
| Timing Recommendation | Key-value display | Action, urgency, reasoning |
| Strategy Comparison | Cards per strategy | Pros/cons, expected outcome |
| Risk Assessment | Risk cards | Category, severity, mitigation |
| Property Recommendations | Property cards | Top picks with reasoning |
| Decision Anchors | Key-value display | Reference points for decisions |

**Action Buttons**:
- "Use in Negotiation" → Navigate to Negotiation page with report context
- "Use in Simulation" → Navigate to Simulation page with report pre-selected

---

### Negotiation Page

**File**: `frontend/src/pages/NegotiationPage.tsx`

**Purpose**: Manual chat with AI agents for property negotiations.

**User Flow**:

```
1. Select user profile from dropdown
2. Select agent role: AI Assistant, Buyer, Seller, or Broker
3. (Optional) Select intelligence report to inform agent decisions
4. Type message → POST /api/agent/message
5. Agent responds with text + tool calls
6. Continue conversation — agent maintains context
```

**Agent Controls**:
- User selector (loads from GET /api/users)
- Role selector (assistant/buyer/seller/broker)
- Report selector (completed reports for selected user)
- Status indicator (Ready / Agent thinking...)

**Message Display**:
- User messages (right-aligned)
- Agent messages (left-aligned) with sender role label
- Expandable tool call details (tool name, input JSON, output JSON)
- Typing indicator with spinner during agent processing

---

### Simulation Page

**File**: `frontend/src/pages/SimulationPage.tsx`

**Purpose**: Run automated multi-round negotiation between buyer and seller agents.

**Configuration Form**:

| Field | Description | Default |
|-------|-------------|---------|
| Property ID | Target property | — |
| Buyer | User profile for buyer agent | — |
| Seller | User profile for seller agent | — |
| Asking Price | Seller's listed price | — |
| Initial Offer | Buyer's opening bid | — |
| Seller Minimum | Seller's walk-away price | — |
| Buyer Maximum | Buyer's ceiling | — |
| Strategy | aggressive / balanced / conservative | balanced |
| Max Rounds | 1-15 | 10 |
| Report | MiroFish report for data-driven decisions | (optional) |

**User Flow**:

```
1. Fill configuration form
2. Click "Start Simulation"
   → POST /api/simulation/start (returns 202 + sim_id)
3. Watch live transcript
   → Poll GET /api/simulation/status/{id} every 2s
   → Progress bar updates with current round
   → Transcript auto-scrolls to latest message
4. View results when complete
   → GET /api/simulation/result/{id}
   → Shows outcome (accepted/rejected/timeout), final price, round count
5. Click "New Simulation" to reset
```

**Transcript Display**:
- Color-coded bubbles: Buyer (blue), Seller (amber), Broker (purple), System (gray)
- Round number labels
- Tool call details per message
- Final result summary card

---

### System Page

**File**: `frontend/src/pages/SystemPage.tsx`

**Purpose**: System health monitoring and metrics.

**Displays**:
- Health status (GET /health)
- Version info
- Prometheus metrics (GET /metrics) — counters, gauges, histograms

---

## MiroFish Intelligence System

MiroFish is the financial intelligence engine that generates deep investment analysis reports. It takes a personalized "seed document" and runs tick-based financial modeling.

### Seed Assembly

**File**: `intelligence/seed_assembly.py`

The seed document is a structured markdown document compiled from multiple data sources:

```
Seed Document (5 sections)
├── Section 1: Investor Profile
│   └── User demographics, budget, timeline, risk tolerance, goals
├── Section 2: Local Market Context
│   └── Market stats, median prices, DOM, inventory, trends
├── Section 3: Investment Decision Framework
│   └── Criteria template for evaluating investments
├── Section 4: Active Listings (top 15)
│   └── Each listing enriched with TomTom neighborhood data
│       (schools, transit, restaurants, parks, walkability score)
└── Section 5: Platform Rules
    └── Deal constraints, offer rules, compliance
```

**Data Sources**:
- **User Profile** → PostgreSQL (UserProfile table)
- **Market Data** → MarketDataService (mock or Zillow provider)
- **Listings** → MarketDataService with optional geohash caching
- **Neighborhood Enrichment** → TomTom Nearby Search API per listing
- **Location Overrides** → Runtime filters from SearchPage (zip, lat/lng, price range)

### Tick-Based Phases

**File**: `intelligence/mirofish_client.py`

The `ticks` parameter (default: 30) controls computation depth. Each phase builds on the previous:

```
Phase 1: Base Financials (ticks 1-5)
├── Parse seed document for property/user data
├── Calculate mortgage amortization schedule
├── Compute monthly cash flow (rental income - expenses)
└── Output: financial_analysis section

Phase 2: Monte Carlo Simulation (ticks 6-15)
├── Run N scenarios (default 300, configurable)
├── Randomize: appreciation (Normal dist), rates (±1.5%),
│   vacancy (3-12%), maintenance (0.8-2%), rental growth (1-5%)
├── Calculate IRR and NPV for each scenario
├── Compute percentiles (p10/p25/p50/p75/p90)
└── Output: monte_carlo_results section

Phase 3: Comparative Analysis (ticks 16-25)
├── Multi-horizon projections (5/10/15/30 years)
│   with bear/base/bull scenarios
├── Rent-vs-buy break-even analysis
├── Tax benefit estimation (mortgage interest, depreciation)
├── Comparable sales analysis from seed data
└── Output: cash_flow_projections, rent_vs_buy_analysis,
    tax_benefit_estimation, comparable_sales_analysis

Phase 4: Synthesis (ticks 26-30)
├── Portfolio-level metrics (Sharpe ratio, max drawdown)
├── Neighborhood scoring aggregation
├── Final investment recommendations
└── Output: portfolio_metrics, neighborhood_scoring,
    market_outlook, timing_recommendation, strategy_comparison,
    risk_assessment, property_recommendations, decision_anchors
```

### Financial Models

**File**: `intelligence/financial_models.py`

Pure math module with no I/O dependencies:

**MortgageCalculator**:
- `monthly_payment(principal, annual_rate, years)` — Standard amortization formula
- `amortization_schedule(principal, annual_rate, years)` — Yearly breakdown with principal/interest split and equity %
- `total_interest(principal, annual_rate, years)` — Total interest over loan term
- Verified: $400k at 6.5% 30yr = $2,528.27/mo

**CashFlowModel**:
- `monthly_cash_flow(rental_income, mortgage, taxes, insurance, ...)` — Returns gross income, effective income (after vacancy), total expenses, net cash flow
- `annual_projections(property_value, rental_income, appreciation, ...)` — Multi-year with appreciation and rental growth

**InvestmentMetrics**:
- `cap_rate(noi, property_value)` — Net Operating Income / Value
- `cash_on_cash(annual_cash_flow, cash_invested)` — Annual return on cash invested
- `irr(cash_flows)` — Internal Rate of Return via Newton's method
- `npv(cash_flows, discount_rate)` — Net Present Value
- `break_even_months(cost_to_own, rent)` — Months until owning beats renting

**MonteCarloEngine**:
- `run_scenarios(base_params, n_scenarios, rng)` — Randomizes key variables, calculates IRR/NPV for each
- Returns: percentile distributions, probability of loss, scenario details

**TaxEstimator**:
- `annual_tax_benefit(mortgage_interest, property_taxes, marginal_rate)` — Itemized deduction savings
- `depreciation_benefit(property_value, land_pct, years)` — Straight-line depreciation (27.5 years for residential)

**PortfolioMetrics**:
- `sharpe_ratio(returns, risk_free_rate)` — Risk-adjusted return
- `max_drawdown(values)` — Largest peak-to-trough decline

### Report Output Structure

The completed report is stored as JSON in `MiroFishReport.report_json`:

```json
{
  "market_outlook": {
    "direction": "moderately_bullish",
    "confidence": 0.72,
    "key_factors": ["low inventory", "rising demand", ...]
  },
  "timing_recommendation": {
    "action": "buy_soon",
    "urgency": "moderate",
    "reasoning": "..."
  },
  "financial_analysis": {
    "mortgage": {
      "monthly_payment": 2528,
      "total_interest": 509777,
      "amortization_summary": { "year_5_equity_pct": 8.2, ... }
    },
    "cash_flow": {
      "monthly_net": 450,
      "annual_projections": [...]
    }
  },
  "monte_carlo_results": {
    "scenarios_run": 300,
    "irr_distribution": { "p10": 3.2, "p25": 5.1, "p50": 7.8, "p75": 10.2, "p90": 13.5 },
    "npv_distribution": { "p10": -15000, "p50": 68000, "p90": 185000 },
    "probability_of_loss": 0.12
  },
  "cash_flow_projections": {
    "horizons": {
      "5_year": { "bear": {...}, "base": {...}, "bull": {...} },
      "10_year": {...}, "15_year": {...}, "30_year": {...}
    }
  },
  "rent_vs_buy_analysis": {
    "break_even_months": 54,
    "scenarios": { "bear": {...}, "base": {...}, "bull": {...} }
  },
  "tax_benefit_estimation": {
    "annual_mortgage_interest_deduction": 18500,
    "depreciation_annual": 11636,
    "estimated_annual_savings": 7400
  },
  "portfolio_metrics": {
    "sharpe_ratio": 0.85,
    "max_drawdown_pct": 15.3,
    "diversification_score": 0.6
  },
  "comparable_sales_analysis": {
    "median_price_psf": 285,
    "value_indicator": "below_market",
    "comparables": [...]
  },
  "neighborhood_scoring": {
    "overall_score": 78,
    "schools": 82, "transit": 75, "dining": 70, "parks": 68
  },
  "strategy_comparison": [...],
  "risk_assessment": [...],
  "property_recommendations": [...],
  "decision_anchors": {...}
}
```

---

## AI Agent System

### Agent Architecture

All agents inherit from `BaseAgent` and follow the same pattern:

```
BaseAgent
├── client: AsyncAnthropic (Claude API)
├── model: claude-sonnet-4-20250514
├── role: AgentRole enum
├── tool_registry: ToolRegistry (name → async handler)
├── _services: { db, event_store, maps, market_data }
│
├── system_prompt() → str (abstract)
├── tools() → list[dict] (abstract)
├── filtered_tools() → tools filtered by role ACL
├── process_message(message, context, history) → { response, tool_calls }
│   1. Build system prompt with injected JSON context
│   2. Call Claude API with filtered tools
│   3. Execute tool calls, validate via ACL
│   4. Collect tool results, re-call Claude if needed
│   5. Return final text response + tool call log
└── execute_tool(name, input) → result
```

### Buyer Agent

**File**: `agent/buyer_agent.py`, prompt in `agent/prompts.py`

**Goal**: Find properties and negotiate the lowest price.

**Strategy**:
- Start 5-12% below asking price
- Never reveal budget ceiling to seller
- Use comparable sales data to justify lower offers
- Recommend acceptance if within 3% of max budget
- Track spread between offers and flag stalls
- Monitor deadline and escalate urgency if <12 hours

**Tools**: search_properties, analyze_neighborhood, place_offer, get_comps, counter_offer, get_intelligence_report

### Seller Agent

**File**: `agent/seller_agent.py`, prompt in `agent/prompts.py`

**Goal**: Price properties optimally and negotiate the highest price.

**Strategy**:
- Price 3-5% above comparable sales median
- Counter when spread is <8%
- Escalate after round 5 if no convergence
- Disclose known issues proactively
- Justify pricing with market data

**Tools**: search_properties, analyze_neighborhood, place_offer, get_comps, counter_offer, get_intelligence_report

### Broker Agent

**File**: `agent/broker_agent.py`

**Goal**: Mediate between buyer and seller, find fair value, close deals.

**Triggers**: Intervenes when spread >10% after round 3, or when prices stall (same offer repeated).

**Tools**: All negotiation tools + mediation-specific tools

### Assistant Agent

**File**: `agent/assistant_agent.py`, prompt in `agent/prompts_assistant.py`

**Goal**: Guide users through investment decisions using reference properties and MiroFish data.

**Workflow**:
1. Profile reference property (from user selection)
2. Run MiroFish analysis (get_intelligence_report — "MOST IMPORTANT TOOL")
3. Analyze reference property financials
4. Search for similar properties
5. Compare candidates on financial metrics, neighborhood scores
6. Recommend with MiroFish-backed reasoning

**Rule**: Every recommendation must be backed by MiroFish data.

**Tools**: search_properties, analyze_neighborhood, place_offer, get_comps, counter_offer, get_intelligence_report

### Tool ACL

**File**: `agent/tool_acl.py`

Defense-in-depth: tools are filtered **before** sending to Claude AND validated **after** Claude responds.

```
AgentRole.BUYER     → search, neighborhood, place_offer, get_comps, counter_offer, get_intelligence_report
AgentRole.SELLER    → search, neighborhood, place_offer, get_comps, counter_offer, get_intelligence_report
AgentRole.BROKER    → search, neighborhood, place_offer, get_comps, counter_offer, get_intelligence_report, mediate
AgentRole.ASSISTANT → search, neighborhood, place_offer, get_comps, counter_offer, get_intelligence_report
```

### Agent Orchestrator

**File**: `agent/orchestrator.py`

The orchestrator acts as a "kernel scheduler" — it routes messages to agents and manages context injection.

```
route_message(user_id, role, message, report_id?)
  1. Select agent by role
  2. Build context:
     - Active negotiations (from DB)
     - Intelligence report (specific or latest completed)
       → Injects: market_outlook, financial_analysis, monte_carlo_results,
         cash_flow_projections, rent_vs_buy, tax_benefits, portfolio_metrics,
         comparable_sales, neighborhood_scoring
  3. Record domain event (agent.message_received)
  4. Call agent.process_message(message, context)
  5. Record domain event (agent.response_sent)
  6. Publish via EventBus (if available)
  7. Commit and return result
```

---

## Negotiation Simulation Engine

**Files**: `services/negotiation_simulator.py`, `agent/simulation_tools.py`

### How It Works

The simulation runs real Claude API calls with all three agents, but uses **in-memory mock tools** instead of writing to the database.

**SimulationState** (in-memory):
```python
@dataclass
class SimulationState:
    negotiation_id: str
    property_id: str
    asking_price: float
    buyer_maximum: float
    seller_minimum: float
    current_round: int
    buyer_latest_price: float
    seller_latest_price: float
    offers: list[dict]      # Full offer history
    status: str             # active / accepted / rejected
```

**Simulation Loop**:

```
For each round (1 to max_rounds):

  ┌─ BUYER TURN ─────────────────────────────┐
  │ Build buyer message with latest seller    │
  │ offer context. Call buyer agent.          │
  │ Extract price from sim_counter_offer or   │
  │ sim_place_offer tool call.                │
  │ Check: Did buyer accept? → End (accepted) │
  │ Check: Did buyer reject? → End (rejected) │
  └───────────────────────────────────────────┘

  ┌─ SELLER TURN ─────────────────────────────┐
  │ Build seller message with buyer's latest  │
  │ offer. Call seller agent.                 │
  │ Extract price from sim_counter_offer.     │
  │ Check: Did seller accept? → End (accepted)│
  │ Check: Did seller reject? → End (rejected)│
  └───────────────────────────────────────────┘

  ┌─ BROKER CHECK (conditional) ──────────────┐
  │ Trigger if: spread >10% after round 3     │
  │         OR: prices stalled (repeated)     │
  │ Broker mediates: suggests fair value,     │
  │ recommends compromise or walk-away        │
  └───────────────────────────────────────────┘
```

**Information Barriers**: Buyer and seller maintain separate conversation histories. Only public offers (prices) are shared between them — internal reasoning is hidden.

**Simulation Tools** (`create_simulation_tools(state)`):
- `sim_place_offer` → Updates state.buyer_latest_price
- `sim_counter_offer` → Updates state prices, calculates spread
- `sim_accept_offer` → Sets status=accepted, records final_price
- `sim_evaluate_offer` → Returns current spread analysis
- `sim_mediate_negotiation` → Broker compromise calculation
- `sim_get_intelligence_report` → Returns MiroFish data from context
- Noop tools for unused agent tools (search, neighborhood, etc.)

**Outcomes**: accepted, rejected, timeout (max rounds), failed (error)

---

## Backend API Reference

### Properties

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/properties/` | List with filters (status, price, type, limit, offset) |
| GET | `/api/properties/{id}` | Get property details |
| POST | `/api/properties/` | Create property |
| PATCH | `/api/properties/{id}` | Update property |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/` | List all users |
| GET | `/api/users/{id}` | Get user profile |
| POST | `/api/users/` | Create user |
| PATCH | `/api/users/{id}` | Update user |

### Reports (MiroFish)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reports/generate` | Start report generation (202) |
| GET | `/api/reports/status/{id}` | Poll generation progress |
| GET | `/api/reports/user/{user_id}` | List user's reports |
| GET | `/api/reports/{id}` | Get completed report JSON |

### Agent

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/agent/message` | Send message to AI agent |

Request: `{ user_id, role, message, report_id? }`
Response: `{ response, tool_calls[], error? }`

### Simulation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/simulation/start` | Start negotiation simulation (202) |
| GET | `/api/simulation/status/{id}` | Get progress + live transcript |
| GET | `/api/simulation/result/{id}` | Get final results (completed only) |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check + version |
| GET | `/metrics` | Prometheus metrics export |

---

## Data Flow Diagrams

### Report Generation Flow

```
User (SearchPage or UsersPage)
  │
  ▼
POST /api/reports/generate
  │ { user_id, question, location_overrides? }
  │
  ▼
Create MiroFishReport record (status=pending)
  │
  ▼
Background Task: _run_report_workflow()
  │
  ├─► Load UserProfile from DB
  ├─► Apply location overrides (zip, lat/lng, price range)
  ├─► Fetch market stats (MarketDataService)
  ├─► Fetch active listings (MarketDataService)
  ├─► Enrich each listing with TomTom neighborhood data
  ├─► Assemble 5-section seed document
  ├─► Run MiroFish simulation (tick-based phases)
  │   ├── Phase 1: Mortgage + Cash Flow
  │   ├── Phase 2: Monte Carlo (300 scenarios)
  │   ├── Phase 3: Rent-vs-Buy, Tax, Comps
  │   └── Phase 4: Portfolio Metrics, Synthesis
  ├─► Parse results → MiroFishReportData
  └─► Save report_json to DB (status=completed)
       │
       ▼
Frontend polls /api/reports/status/{id} (every 1.5s)
  │ Shows: progress bar + current step name
  │
  ▼
GET /api/reports/{id} → Full report with all sections
```

### Agent Message Flow

```
User (NegotiationPage or SearchPage Assistant)
  │ { user_id, role, message, report_id? }
  │
  ▼
POST /api/agent/message
  │
  ▼
AgentOrchestrator.route_message()
  ├─► Select agent by role
  ├─► Build context:
  │   ├── Active negotiations (from DB)
  │   └── Intelligence report (financial_analysis, monte_carlo, etc.)
  ├─► Record event: agent.message_received
  │
  ▼
Agent.process_message()
  ├─► Inject context JSON into system prompt
  ├─► Call Claude API (claude-sonnet-4) with filtered tools
  ├─► Claude responds with text + tool_use blocks
  ├─► Execute each tool call:
  │   ├── Validate via ACL
  │   ├── Run tool handler (search DB, call TomTom, etc.)
  │   └── Feed result back to Claude
  ├─► Claude generates final text response
  │
  ▼
Return { response, tool_calls[] } → Display in chat UI
```

### Simulation Flow

```
User (SimulationPage)
  │ { property_id, buyer_id, seller_id, prices, strategy, report_id? }
  │
  ▼
POST /api/simulation/start
  │
  ▼
Create NegotiationSimulator
  ├── SimulationState (in-memory)
  ├── BuyerAgent + SellerAgent + BrokerAgent
  ├── Simulation tools (mock, no DB writes)
  └── Load MiroFish report if report_id provided
       │
       ▼
Background Task: simulator.run()
  │
  For round in 1..max_rounds:
  │ ┌── Buyer Turn ──────────────────┐
  │ │ Claude API call with buyer     │
  │ │ prompt + negotiation context   │
  │ │ → sim_place_offer / sim_counter│
  │ │ → Check accept/reject          │
  │ └────────────────────────────────┘
  │ ┌── Seller Turn ─────────────────┐
  │ │ Claude API call with seller    │
  │ │ prompt + buyer's offer         │
  │ │ → sim_counter_offer            │
  │ │ → Check accept/reject          │
  │ └────────────────────────────────┘
  │ ┌── Broker (if triggered) ───────┐
  │ │ Mediation if spread >10%       │
  │ │ or prices stalled              │
  │ └────────────────────────────────┘
  │
  ▼
Frontend polls /api/simulation/status/{id} (every 2s)
  │ Shows: progress bar, live transcript, round counter
  │
  ▼
GET /api/simulation/result/{id} → outcome, final_price, full transcript
```

---

## Database Models

**File**: `db/models.py`

| Table | Purpose | Key Fields |
|-------|---------|------------|
| **UserProfile** | Investor/seller profiles | budget_min/max, risk_tolerance, timeline_days, location, preferred_types |
| **Property** | Real estate listings | address, asking_price, beds/baths/sqft, type, status, neighborhood_data |
| **Offer** | Purchase offers | property_id, buyer_id, offer_price, contingencies, status, parent_offer_id |
| **Negotiation** | Negotiation sessions | buyer_id, seller_id, status (11 states), round_count, deadline_at, final_price |
| **AgentDecision** | AI decision audit trail | agent_type, action, reasoning, tool_used, tool_input/output |
| **AgentMemory** | Agent key-value store | agent_type, user_id, key, value (JSONB) |
| **MiroFishReport** | Intelligence reports | user_id, status, simulation_config, report_json (JSONB) |
| **MiroFishSeed** | Seed document archive | user_id, seed_text, market_data_snapshot, listings_snapshot |
| **DomainEvent** | Event sourcing log | event_type, aggregate_type/id, payload, correlation_id, sequence |

**Negotiation States**: idle → offer_pending → counter_pending → accepted/rejected/withdrawn/escalated → contract_phase → inspection → closing → closed

---

## External Integrations

### TomTom Maps API

**Service**: `services/maps.py`

- **Geocoding**: Address → lat/lng coordinates
- **Nearby Search**: POIs within radius (schools, transit, restaurants, parks, grocery, hospital)
- **Walkability Score**: Calculated from POI density (min(100, total_places * 5))
- **Free Tier**: 2,500 non-tile requests/day
- **Base URL**: `https://api.tomtom.com/search/2`

### Claude API (Anthropic)

- **Model**: claude-sonnet-4-20250514
- **Max Tokens**: 4,096 per response
- **Usage**: All agent conversations and simulation turns
- **Tool Use**: Claude calls tools defined by each agent, results fed back for final response

### Market Data

**Service**: `services/market_data.py` with provider pattern

- **Mock Provider**: Synthetic data for development
- **Zillow Provider**: Real market data (when configured)
- **Data**: Market stats (median price, DOM, inventory), active listings, comparable sales

### Redis

- **Pub/Sub**: Real-time event distribution (negotiation events, agent events, timeouts)
- **Channels**: `negotiation:{id}`, `agent:{type}:{user_id}`, `system:timeout`

---

## Configuration

**File**: `config.py` (Pydantic BaseSettings, loaded from environment)

| Setting | Default | Description |
|---------|---------|-------------|
| `anthropic_api_key` | — | Claude API key |
| `tomtom_api_key` | — | TomTom Maps API key |
| `database_url` | postgresql+asyncpg://... | PostgreSQL connection |
| `redis_url` | redis://localhost:6379/0 | Redis connection |
| `mirofish_mode` | "mock" | "mock" or "live" |
| `monte_carlo_scenarios` | 300 | Number of Monte Carlo simulations |
| `max_simulation_rounds` | 15 | Maximum negotiation simulation rounds |
| `market_data_provider` | "mock" | "mock" or "zillow" |
| `max_deal_value_auto` | 2,000,000 | Auto-approval ceiling |
| `min_offer_percent` | 0.50 | Minimum offer as % of asking |
| `max_counter_rounds` | 10 | Max counter-offer rounds |
