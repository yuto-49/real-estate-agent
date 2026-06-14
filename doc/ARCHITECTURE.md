# Architecture Overview

## System Diagram

```
Browser (React 18 + Vite)
  |
  +-- Supabase Auth (JWT)
  +-- REST API calls (/api/*)
  +-- WebSocket (/ws/*)
        |
        v
   Caddy (reverse proxy, prod only)
        |
        v
   FastAPI Application (main.py)
   +-- Middleware: CORS, Correlation ID, JWT verification
   +-- API Routers (api/)
   |   +-- Properties & Search -- CRUD, rent comps, market context
   |   +-- Portfolio & Holdings -- investor portfolios, financials
   |   +-- Simulation -- market replay, property sim, unified sim
   |   +-- Strategy -- underwriting, stress test, strategy runs
   |   +-- Users & Onboarding -- profiles, investor onboarding
   |   +-- Signals -- REINFOLIB, external market data
   |
   +-- Domain Layer (domain/) -- PURE, no I/O
   |   +-- Events -- canonical event taxonomy
   |   +-- Market -- MarketContextSnapshot, market signals
   |   +-- Actors -- investor/household signal projections
   |   +-- Reactions -- ReactionVector, narrative clustering
   |   +-- Decisions -- state machine, pluggable policies
   |   +-- Outcomes -- market projections, snapshots
   |   +-- Reports -- underwriting, briefings, replay
   |
   +-- Services (services/) -- orchestration + I/O
   |   +-- Market State -- build_snapshot from DB signals
   |   +-- Signal Writer -- idempotent per-day upsert
   |   +-- Signal Providers -- pluggable external data (REINFOLIB, e-Stat)
   |   +-- Strategy Runner -- in-process strategy execution
   |   +-- Portfolio Summary -- aggregation + analysis
   |   +-- Redis, Pub/Sub, Metrics, Maps, Logging
   |
   +-- Intelligence (intelligence/) -- financial models
   |   +-- Underwriting (cap rate, CoC, DSCR, IRR)
   |   +-- Monte Carlo stress test
   |   +-- MiroFish pipeline (seed -> HTTP -> parse -> report)
   |
   +-- Agent System (agent/) -- Claude AI agents
       +-- Orchestrator -> Buyer/Seller/Broker/Assistant agents
       +-- Tool ACL (frozen permission map)
       +-- Guardrails (business rule enforcement)
       +-- Tool handlers (search, comps, offers, intelligence)
        |
        v
   PostgreSQL (async SQLAlchemy 2.0 + Alembic migrations)
   Redis (caching, pub/sub, job queue)
```

## Key Boundaries

| Boundary | Rule |
|----------|------|
| `domain/` | Pure Python, no I/O, no DB/Redis/HTTP calls. Deterministic projections only. |
| `services/` | Orchestration layer. Bridges domain logic to DB/Redis/external APIs. |
| `api/` | HTTP interface. Thin -- delegates to services and domain. |
| `agent/` | Claude API integration. Tool calls gated by ACL. |
| `intelligence/` | Financial computation. No direct DB access -- receives data, returns results. |

## Data Flow: Market Signal Pipeline

```
External Source (REINFOLIB, e-Stat)
  -> Signal Provider (services/signal_providers/)
    -> Signal Writer (services/signal_writer.py) -- idempotent upsert
      -> MarketSignal table (db/models.py)
        -> build_snapshot() (services/market_state.py)
          -> MarketContextSnapshot (domain/market/)
            -> Consumed by: decisions, underwriting, portfolio summary, frontend
```

## Data Flow: Investment Page

```
InvestmentPage (shared state: userId, portfolioId)
  +-- DashboardSection  -> GET /api/portfolio/summary
  +-- PortfolioSection  -> GET /api/portfolio/holdings, /api/decisions/holding/{id}
  +-- AnalysisSection   -> POST /api/listings/analyze, GET /api/listings/reports
  +-- SimulationSection
  |   +-- Market Replay -> POST /api/simulation/market/personas -> /market/start -> /market/replay
  |   +-- Property Sim  -> POST /api/simulation/run
  +-- StrategySection   -> POST /api/underwrite/run, /api/strategy/run
```

## Database: Core Models (23 tables)

See `db/models.py` for full schema. Key model groups:

- **Property**: Property, MarketSignal
- **User**: UserProfile, InvestorPortfolio, PortfolioHolding, HoldingFinancials
- **Negotiation**: Offer, Negotiation, AgentDecision, AgentMemory
- **Simulation**: SimulationResult, MarketSimulationRun, SocialSimulationRun
- **Domain**: DomainEvent, UnderwritingScenario
- **Social**: HouseholdProfile, HouseholdSocialEdge, MiroFishReport, MiroFishSeed

## External Integrations

| Service | Config Key | Purpose |
|---------|-----------|---------|
| Supabase | `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Auth (JWT), user management |
| Anthropic Claude | `ANTHROPIC_API_KEY` | AI agents for negotiation/analysis |
| REINFOLIB | `REINFOLIB_API_KEY` | Japanese govt real estate data (MLIT) |
| e-Stat | `ESTAT_APP_ID` | Japanese government statistics |
| TomTom | `TOMTOM_API_KEY` | Maps and geocoding |
