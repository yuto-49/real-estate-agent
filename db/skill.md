# db/ — Database Layer

## Purpose
SQLAlchemy 2.0 async ORM models, engine configuration, and session management for PostgreSQL (asyncpg driver). In-memory SQLite used for testing.

## Key Files

| File | Role |
|------|------|
| `database.py` | Async engine factory, `async_session` maker, `get_db()` dependency |
| `models.py` | ~20+ SQLAlchemy models with UUID primary keys, JSONB columns, and enums |

## Key Models
- `UserProfile` — user with `preferred_mode`, life stage, risk tolerance
- `Property` — listings with JP-aware columns (JPY prices, tsubo, etc.)
- `InvestorPortfolio`, `PortfolioHolding`, `HoldingFinancials` — portfolio stack
- `UnderwritingScenario` — stored underwriting runs
- `MarketSignal` — time-series market data (signal_type, subject_type, subject_id)
- `Offer`, `Negotiation`, `AgentDecision`, `AgentMemory` — negotiation state
- `HouseholdProfile`, `HouseholdSocialEdge` — social simulation personas
- `SocialSimulationRun`, `MarketSimulationRun` — simulation tracking
- `DomainEvent` — event sourcing backbone
- `MiroFishReport`, `MiroFishSeed` — intelligence pipeline artifacts

## Patterns
- **UUID PKs** on all models
- **JSONB** for flexible structured data (disclosures, payloads, snapshots)
- **Async SQLAlchemy 2.0** — `select()` style, no legacy Query API
- **Enum columns** for LifeStage, RiskTolerance, PropertyStatus
