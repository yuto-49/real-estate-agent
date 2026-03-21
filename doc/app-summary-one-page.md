# Real Estate Agentic Platform - One-Page Summary

## What It Is
A full-stack real estate workflow app that combines a FastAPI backend, React frontend, and AI agents for property analysis and buyer-seller-broker negotiation. It also runs intelligence report workflows and scenario-based negotiation simulations.

## Who It Is For
- Primary persona: an investment-focused real estate user managing an "Active Investor Profile" and using AI-assisted decisions (repo evidence: dashboard/user/report flows).
- Formal persona document: **Not found in repo.**

## What It Does
- Manages user/investor profiles, budgets, goals, and search preferences.
- Lists and filters properties and visualizes them on interactive maps.
- Generates intelligence reports with multi-step progress tracking.
- Runs multi-scenario negotiation simulations with generated buyer/seller personas.
- Compares simulation outcomes (win rate, best scenario, price path).
- Provides agent chat with buyer/seller/broker/assistant roles and tool-call traces.
- Exposes system health and metrics in-app.

## How It Works (Repo-Evidenced)
- **Frontend:** React + TypeScript + Vite (`frontend/src/*`) with pages for dashboard, analysis, simulation, negotiation, and profile.
- **API layer:** FastAPI routers mounted in `main.py` (`/api/properties`, `/api/reports`, `/api/simulation`, `/api/agent`, `/ws`, etc.).
- **Core services:** report workflow (`api/reports.py` + `intelligence/*`), negotiation simulation (`services/negotiation_simulator.py`, `services/batch_simulator.py`), mapping/market adapters (`services/maps.py`, `services/market_data.py`).
- **Data layer:** SQLAlchemy models + async sessions (`db/models.py`, `db/database.py`), Alembic migrations, plus Redis-backed services (pub/sub, cache, queue).
- **Typical flow:** UI action -> API endpoint -> service/orchestrator -> DB/Redis/external intelligence -> status/results returned to UI.

## How to Run (Minimal)
1. `docker compose up -d db redis`
2. `pip install -e ".[dev]"`
3. `cp .env.example .env`
4. `alembic upgrade head && python scripts/seed_properties.py`
5. `uvicorn main:app --reload`
6. (Frontend) `cd frontend && npm install && npm run dev`

## UI/UX Findings and Improvement Plan
- **Flaw 1 (does not work):** Top-nav `Profile` links to `/profile` but page expects `:id`; without ID, `UserProfilePage` can stay in loading state.
- **Flaw 2:** Simulation "Max Rounds" slider is shown but not sent in batch request payload, so control appears ineffective.
- **Flaw 3:** Search location selector does not filter API results and map center updates are not reacted to after initial map mount, so location behavior can feel misleading.
- **Figma MCP design source:** Figma URL/node reference **Not found in repo**, so MCP design-context pull cannot be run from repo artifacts alone.

1. **P0 - Fix broken profile route flow:** redirect `/profile` to selected user profile or show explicit picker when no `id`.
2. **P1 - Wire simulation controls end-to-end:** pass `max_rounds` from UI -> API schema -> batch simulator config; display applied value per scenario.
3. **P1 - Make search location behavior honest:** either apply location filters backend-side or relabel as "Map focus"; also add map recenter effect when `center` prop changes.
4. **P2 - Improve UX resilience:** add empty-state CTAs, explicit loading/error recovery patterns, and mobile-first spacing checks for dense tables/chat.
