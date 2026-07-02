# api/ — FastAPI Route Layer

## Purpose
FastAPI routers exposing all HTTP endpoints for the platform: investor workflows, property search, portfolio management, underwriting, strategy simulation, social simulation, and WebSocket events.

## Key Files

| File | Role |
|------|------|
| `listing_analysis.py` | `POST /listings/{id}/analyze` — triggers analyst council review |
| `portfolio.py` | Portfolio CRUD + `/summary` aggregator |
| `decisions.py` | `GET /api/decisions/holding/{id}` — holding decision recommendations |
| `strategy.py` | Strategy run endpoints — execute and query strategy simulations |
| `underwrite.py` | Property underwriting + listing parse |
| `properties.py` | Property CRUD, market context read API |
| `onboarding.py` | User onboarding wizard flow |
| `users.py` | User profile management |
| `investor_profile.py` | Investor-specific profile settings |
| `search.py` | Property discovery and filtering |
| `schemas.py` | All Pydantic request/response DTOs |
| `public_config.py` | Static public configuration endpoint |

## Patterns
- **Dependency injection:** DB sessions via FastAPI `Depends(get_db)`
- **Correlation IDs:** All requests carry UUID from middleware
- **Auth:** Supabase JWT verification via middleware (passthrough when unconfigured)
- **Async-first:** All route handlers are async

## Dependencies
- `db/` (models, session)
- `services/` (business logic)
- `domain/` (pure projections)
- `intelligence/` (financial math)
- `middleware/` (auth, correlation)
