# Architecture — Real Estate Agentic Platform

## 1. System Purpose

This platform simulates and executes real estate transactions with a focus on **workforce housing** — affordable, regulation-compliant housing for essential workers, moderate-income families, and community-stabilization programs. It uses multi-agent AI orchestration, social behavior simulation, and swarm intelligence to produce legally defensible, data-driven housing decisions.

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│   React 18 + TypeScript + Vite                                               │
│   ┌──────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────┐ │
│   │Dashboard │ │ Negotiation  │ │  Simulation  │ │ Analysis │ │  Profile │ │
│   │  + Map   │ │    Chat      │ │   Runner     │ │ Reports  │ │  Editor  │ │
│   └────┬─────┘ └──────┬───────┘ └──────┬───────┘ └────┬─────┘ └────┬─────┘ │
│        │               │ WebSocket      │              │            │        │
└────────┼───────────────┼────────────────┼──────────────┼────────────┼────────┘
         │               │                │              │            │
┌────────▼───────────────▼────────────────▼──────────────▼────────────▼────────┐
│                            API GATEWAY (FastAPI)                              │
│   Middleware: Correlation ID · JWT Auth · Rate Limiting · CORS               │
│                                                                              │
│   Routers:                                                                   │
│   /api/properties  /api/offers  /api/users  /api/negotiations                │
│   /api/reports     /api/simulation  /api/simulation/batch                    │
│   /api/agent       /api/webhooks    /api/social-sim (planned)                │
│   /ws/negotiation/{id}  /health  /metrics                                    │
└────────┬───────────────┬────────────────┬──────────────┬────────────────────-┘
         │               │                │              │
┌────────▼───────┐ ┌─────▼──────┐ ┌───────▼──────┐ ┌────▼──────────────────┐
│  AGENT SYSTEM  │ │ NEGOTIATION│ │  SIMULATION  │ │    INTELLIGENCE       │
│                │ │   ENGINE   │ │    ENGINE    │ │      PIPELINE         │
│ Orchestrator   │ │            │ │              │ │                       │
│ ┌───────────┐  │ │ State      │ │ Negotiation  │ │ Seed Assembly         │
│ │  Buyer    │  │ │ Machine    │ │ Simulator    │ │ (market context,      │
│ │  Agent    │  │ │            │ │              │ │  investor profile,    │
│ ├───────────┤  │ │ ZOPA       │ │ Batch        │ │  listings snapshot)   │
│ │  Seller   │  │ │ Detection  │ │ Simulator    │ │          │            │
│ │  Agent    │  │ │            │ │              │ │          ▼            │
│ ├───────────┤  │ │ Timeout    │ │ Persona      │ │ MiroFish Client       │
│ │  Broker   │  │ │ Enforcer   │ │ Generator    │ │ (circuit breaker,     │
│ │  Agent    │  │ │            │ │              │ │  retry, backoff)      │
│ ├───────────┤  │ │ Guardrails │ │ Scenario     │ │          │            │
│ │ Assistant │  │ │            │ │ Variants     │ │          ▼            │
│ │  Agent    │  │ │ Domain     │ │              │ │ Financial Models      │
│ └───────────┘  │ │ Events     │ │ Social       │ │ (Monte Carlo, DCF,    │
│                │ │            │ │ Simulator    │ │  tax, rent-vs-buy)    │
│ Tool ACL       │ │            │ │ (planned)    │ │          │            │
│ Tool Registry  │ │            │ │              │ │          ▼            │
│ Prompts v2.0   │ │            │ │              │ │ Report Parser         │
└────────────────┘ └────────────┘ └──────────────┘ └───────────────────────┘
         │               │                │              │
┌────────▼───────────────▼────────────────▼──────────────▼────────────────────┐
│                          DATA & MESSAGING LAYER                              │
│                                                                              │
│  ┌─────────────────────────┐    ┌───────────────────────────────────────┐    │
│  │      PostgreSQL 16      │    │            Redis 7                    │    │
│  │                         │    │                                       │    │
│  │  user_profiles          │    │  Pub/Sub channels                     │    │
│  │  properties             │    │    negotiation:{id}                   │    │
│  │  offers                 │    │    simulation:{id}                    │    │
│  │  negotiations           │    │                                       │    │
│  │  agent_decisions        │    │  Geocache (geohash → neighborhood)    │    │
│  │  agent_memory           │    │  Rate limit counters                  │    │
│  │  mirofish_reports       │    │  Job queue (Redis Streams)            │    │
│  │  mirofish_seeds         │    │  Session cache                        │    │
│  │  simulation_results     │    │                                       │    │
│  │  domain_events          │    │                                       │    │
│  │                         │    │                                       │    │
│  │  (planned)              │    │                                       │    │
│  │  household_profiles     │    │                                       │    │
│  │  household_social_edges │    │                                       │    │
│  │  social_simulation_runs │    │                                       │    │
│  │  social_sim_actions     │    │                                       │    │
│  └─────────────────────────┘    └───────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────-┘
         │                                    │
┌────────▼────────────────────────────────────▼───────────────────────────────┐
│                       EXTERNAL SERVICES                                     │
│                                                                             │
│  Claude API (Anthropic)     TomTom Maps API       MiroFish Simulation       │
│  - Agent conversations      - Geocoding           - Swarm intelligence      │
│  - Social opinion rounds    - Neighborhood POIs   - Market prediction       │
│  - Persona reasoning        - Route analysis      - Risk assessment         │
│                                                                             │
│  (Future) Zillow API        (Future) ATTOM API                              │
│  - Live market data         - Property records                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Workforce Housing — Operational Model

Workforce housing operates under unique constraints compared to market-rate real estate. This platform models those constraints explicitly.

### 3.1 What Makes Workforce Housing Different

| Dimension | Market-Rate | Workforce Housing |
|-----------|-------------|-------------------|
| **Price ceiling** | Market-driven | Capped at Area Median Income (AMI) affordability thresholds (typically 60-120% AMI) |
| **Tenant qualification** | Credit + income | Income bands, employment verification, household size, sometimes employer affiliation |
| **Regulatory overlay** | Standard zoning | LIHTC, inclusionary zoning, community land trusts, Section 8 project-based, municipal affordable housing ordinances |
| **Financing** | Conventional | Tax credit equity (4%/9% LIHTC), soft seconds, HOME/CDBG funds, state HFA bonds, employer-assisted housing programs |
| **Disposition restrictions** | None | Deed restrictions, affordability covenants (15-99 year terms), right of first refusal, resale price formulas |
| **Stakeholder complexity** | Buyer-seller | Buyer, seller, housing authority, employer, community groups, lenders, tax credit investors, compliance monitors |

### 3.2 How the Platform Simulates Workforce Housing Operations

**Income-Qualified Negotiation:**
The agent system uses `UserProfile.budget_min/budget_max` in conjunction with AMI thresholds to enforce affordability ceilings. The `Guardrails` module validates that offers stay within income-qualified ranges, not just market-reasonable ranges.

**Multi-Stakeholder Negotiation:**
The broker agent mediates not just between buyer and seller but also represents regulatory constraints — ensuring that negotiated prices comply with affordability covenants and that closing timelines accommodate compliance review periods.

**Social Simulation for Community Impact:**
The social simulation engine (planned) models how housing decisions affect neighborhood-level opinion dynamics — critical for workforce housing projects that require community support or face NIMBY opposition. Simulating household-level sentiment around topics like `voucher_program`, `neighborhood_safety`, and `eviction_policy` produces intelligence that informs:
- Site selection (which neighborhoods have favorable sentiment?)
- Community engagement strategy (which household clusters are vocal?)
- Political feasibility (will the policy support score hold through public comment?)

**Financial Modeling with Subsidy Layers:**
The Monte Carlo engine (`intelligence/financial_models.py`) models cash flows with multiple subsidy inputs — LIHTC equity, soft debt, operating subsidies — that have different timing, compliance triggers, and clawback risks. The rent-vs-buy analysis accounts for deed-restricted resale formulas, not just market appreciation.

---

## 4. Legal Reliability and Regulatory Strength

### 4.1 Audit Trail — Event Sourcing

Every state change in the system writes an immutable `DomainEvent` record:

```
domain_events:
  id              UUID (PK)
  correlation_id  UUID (links all events from one request)
  event_type      TEXT (offer_placed, counter_submitted, negotiation_accepted, ...)
  aggregate_type  TEXT (negotiation, property, offer)
  aggregate_id    UUID
  payload         JSONB (full event data)
  actor_type      TEXT (buyer_agent, seller_agent, broker_agent, system)
  actor_id        UUID
  sequence        INTEGER (monotonic per aggregate)
  created_at      TIMESTAMP
```

**Why this matters for regulatory compliance:**
- Fair Housing Act requires demonstrating non-discriminatory treatment — event replay shows exactly what data each agent used and why
- LIHTC compliance audits require showing that qualification and pricing decisions followed program rules — every agent decision is traceable
- Anti-steering regulations require proving that recommendations were based on objective criteria — tool inputs/outputs are recorded in `agent_decisions`

### 4.2 Agent Decision Logging

Every Claude API tool call is recorded in `agent_decisions` with:
- The agent role that made the decision
- The tool used and its exact input/output
- The reasoning chain
- Correlation ID linking it to the broader transaction

This creates a **defensible paper trail** that shows the AI's reasoning can be audited, not just its outcomes.

### 4.3 Guardrail Enforcement

Hard-coded business rules in `agent/guardrails.py`:

| Rule | Purpose | Regulatory Basis |
|------|---------|-----------------|
| Offer >= 50% of asking | Prevents predatory lowball offers | Fair dealing requirements |
| Max auto-approved deal value: $2M | Human review for high-value transactions | Fiduciary duty, institutional compliance policies |
| Max counter rounds: 10 | Prevents infinite negotiation loops | Statute of limitations on offer validity |
| Statutory deadlines (48h/10d/30d) | Enforces time-bound obligations | State real estate contract law (inspection periods, closing timelines) |

### 4.4 Tool ACL — Role-Based Access Control

The frozen permission map in `agent/tool_acl.py` ensures:
- A buyer agent cannot list a property (seller-only action)
- A seller agent cannot search properties (buyer-only action)
- A broker agent has mediation and contract tools but not offer-placement

This prevents agents from taking unauthorized actions, which is critical when the platform is used in regulated contexts where unauthorized agency actions could create legal liability.

### 4.5 Correlation ID Tracing

Every HTTP request receives a UUID that propagates through:
- Middleware → API handler → Agent call → Tool execution → Domain event → Redis pub/sub → WebSocket

This means any regulator, auditor, or compliance officer can trace a single user action through the entire system by querying one correlation ID.

### 4.6 Social Simulation as Regulatory Evidence

When the social simulation engine is complete, it produces:
- **Opinion convergence data** — demonstrates that housing decisions were informed by community input modeling, not just developer preference
- **Narrative cluster analysis** — shows which community concerns were identified and how they informed project design
- **Policy support scoring** — quantifies community sentiment, providing defensible evidence for public hearing submissions

This is particularly valuable for:
- **Environmental Impact Reports** that require community impact assessment
- **Community Reinvestment Act (CRA)** evaluations that measure community development impact
- **Tax credit applications** (LIHTC, New Markets) that require demonstrating community need and support

---

## 5. Core Simulation Components

### 5.1 Negotiation Simulator

**Location:** `services/negotiation_simulator.py`

The core simulation engine that runs buyer, seller, and broker agents against each other in multi-turn negotiations:

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Buyer   │────→│  Engine  │←────│  Seller  │
│  Agent   │     │          │     │  Agent   │
└──────────┘     │  ZOPA    │     └──────────┘
                 │  Detect  │
                 │          │     ┌──────────┐
                 │  State   │←────│  Broker  │
                 │  Machine │     │  Agent   │
                 └──────────┘     └──────────┘
                      │
              ┌───────┼───────┐
              ▼       ▼       ▼
          Domain   Simulation  Agent
          Events   Results     Decisions
```

**Configurable parameters:**
- Initial offer strategy (% below asking)
- Counter-offer strategy (split difference, hold firm, escalate)
- Max rounds, timeout thresholds
- Persona traits (risk tolerance, negotiation style, experience)
- Market scenario (bullish, bearish, stagnant)

### 5.2 Batch Simulator

**Location:** `services/batch_simulator.py`

Runs N scenarios in parallel with variant parameters:
- Cross-product of personas × market scenarios × strategy variants
- Aggregates results: median final price, settlement rate, average rounds
- Identifies optimal strategies per persona-scenario combination

### 5.3 Persona Generator

**Location:** `services/persona_generator.py`

Generates synthetic buyer/seller profiles with:
- MBTI personality type → negotiation behavior mapping
- Risk profile (conservative, moderate, aggressive)
- Experience level → patience and concession patterns
- Life stage → urgency and flexibility parameters

### 5.4 Social Behavior Simulator (Planned)

**Location:** `services/social_simulator.py` (to be implemented)

Models opinion dynamics across a synthetic household network:

```
Round N:
  For each active household:
    1. Gather neighbor opinions (weighted by edge type + influence)
    2. Claude API generates stance update given social context
    3. Apply opinion drift formula:
       new = (stability × current) + ((1 - stability) × neighbor_avg) + LLM_delta
    4. Record action to DB
  Check convergence: mean |opinion_delta| < 0.02 → stop
  Build narrative clusters from final opinion distribution
```

**Social graph edges:**
- `neighbor` (same zip code, weight 0.6-0.9)
- `income_peer` (same income band, weight 0.3-0.6)
- `language_peer` (same primary language, weight 0.5-0.8)
- `demographic` (similar household composition, weight 0.2-0.4)

**Topics modeled:**
- `market_prices` — household sentiment on local price trends
- `eviction_policy` — support/opposition to tenant protections
- `voucher_program` — acceptance of housing choice vouchers in neighborhood
- `neighborhood_safety` — perceived safety and willingness to invest

### 5.5 Intelligence Pipeline

**Location:** `intelligence/`

```
UserProfile + Market Data + Active Listings
         │
         ▼
   Seed Assembly (5-section document)
         │
         ▼
   MiroFish Client (circuit breaker + retry)
         │
         ▼
   MiroFishReportData:
   - market_outlook
   - timing_recommendation
   - strategy_comparison
   - risk_assessment
   - property_recommendations
   - financial_analysis (Monte Carlo, DCF, tax)
   - comparable_sales_analysis
   - neighborhood_scoring
         │
         ▼
   Agent Briefings (role-specific intelligence summaries)
         │
         ▼
   Negotiation Simulation (agents use intelligence to inform strategy)
```

---

## 6. Main Process Flows

### 6.1 Property Search → Intelligence → Negotiation → Closing

```
1. USER creates profile (budget, location, risk tolerance, life stage)
2. BUYER AGENT searches properties (filters: price, type, location)
3. BUYER AGENT analyzes neighborhoods (TomTom → geocache → amenity scoring)
4. INTELLIGENCE PIPELINE assembles seed → MiroFish simulation → report
5. USER selects property → START NEGOTIATION
6. ENGINE: buyer opens at 5-12% below asking
7. ENGINE: seller counters (split difference, hold firm, or reject)
8. LOOP: counter-offer rounds with ZOPA monitoring
   - Round 5+: convergence hints if spread <= 3%
   - Round 5+ spread > 10%: broker mediation auto-triggered
   - Round 10+: auto-escalation
9. ACCEPTANCE → CONTRACT_PHASE (72h) → INSPECTION (10d) → CLOSING (30d) → CLOSED
10. All events recorded, all decisions auditable
```

### 6.2 Simulation Flow (Testing Strategy Before Commitment)

```
1. USER configures simulation (property, personas, market scenario)
2. BATCH SIMULATOR generates scenario matrix (personas × strategies × markets)
3. For each scenario:
   a. PERSONA GENERATOR creates buyer/seller profiles
   b. NEGOTIATION SIMULATOR runs full multi-turn negotiation
   c. Results recorded: final price, rounds, settlement rate, price path
4. AGGREGATION: compare scenarios, identify optimal strategy
5. USER reviews results → selects strategy → starts real negotiation
```

### 6.3 Social Simulation → Report → Negotiation (Planned)

```
1. GENERATE synthetic households for target zip codes
2. BUILD social graph (neighbor, income, language, demographic edges)
3. RUN opinion rounds:
   - Each household considers neighbor opinions + Claude reasoning
   - Opinion drift formula applied per round
   - Convergence detection at delta < 0.02
4. BUILD narrative clusters from final opinion distribution
5. TRANSLATE social output → MiroFishReport format
6. FEED report into negotiation simulation as intelligence briefing
7. AGENTS use community sentiment data to inform strategy:
   - Buyer: neighborhood satisfaction → offer confidence
   - Seller: community support → pricing justification
   - Broker: policy sentiment → compliance guidance
```

---

## 7. Deployment Architecture

### Development
```
Local machine:
  uvicorn main:app --reload (port 8000)
  npm run dev (port 5173, proxies to 8000)

Shared Docker services:
  dev-postgres (port 5432)
  dev-redis (port 6379)
```

### Production
```
docker-compose.prod.yml:
  app: 2 replicas, 4 workers each, 1 CPU / 1GB RAM limit
  db:  PostgreSQL 16, named volume, health check
  redis: Redis 7, 256MB maxmemory, allkeys-lru eviction
```

---

## 8. Security Model

| Layer | Mechanism |
|-------|-----------|
| **Authentication** | JWT (HMAC-signed) via `middleware/auth.py` |
| **Rate Limiting** | Redis sliding-window per IP via `middleware/rate_limit.py` |
| **Agent Authorization** | Frozen tool ACL map — agents cannot exceed their role permissions |
| **Webhook Integrity** | HMAC verification on MiroFish callbacks |
| **Input Validation** | Pydantic v2 schemas on all API endpoints |
| **Business Rules** | Guardrails module blocks invalid offers and unauthorized deal sizes |
| **Correlation Tracing** | Full request-to-event tracing via UUID correlation IDs |

---

## 9. Technology Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **AI** | Claude API (Anthropic), tool-use with ACL |
| **Database** | PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic |
| **Cache/Queue** | Redis 7 (pub/sub, geocache, rate limiting, job queue via Streams) |
| **Frontend** | React 18, TypeScript, Vite, WebSocket |
| **Maps** | TomTom Maps API (geocoding, POI search, neighborhood analysis) |
| **Intelligence** | MiroFish (swarm simulation), Monte Carlo, DCF, tax models |
| **Observability** | structlog, correlation IDs, domain events, in-memory metrics |
| **Testing** | pytest-asyncio, in-memory SQLite, fakeredis, 70+ tests |
| **Containerization** | Docker Compose (dev + prod profiles) |
