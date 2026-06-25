# Remove Negotiation/Social-Sim & Add Analysis + Simulation Portfolio Tabs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) tracking.

**Goal:** Delete the orphaned negotiation/social-sim frontend surface and leftover backend artifacts; rebrand Overview→Analysis; absorb the Strategy tab into a free-text Simulation tab; audit all strategy runs to `domain_events`.

**Branch:** `claude/backend-domain-usage-9zqifv`.

## Global Constraints
- `domain/` stays pure/deterministic/side-effect-free/lenient — untouched.
- Async-first; DI'd DB sessions; Pydantic v2; UUID PKs; structlog (no print).
- New state changes → `domain_events` with correlation id (via `services/event_store.py::EventStore`).
- Tests in `tests/` (in-memory SQLite, fakeredis, no network). `pytest tests/ -v` stays green.
- `get_db` does NOT commit — explicit `await db.commit()` required when persisting.

---

## Phase 1 — Backend: audit strategy runs to domain_events
- Task 1.1: `execute_strategy_run` gains `correlation_id` param; appends `strategy.run_started/completed/failed` via `EventStore`; explicit commit. Test `tests/test_strategy_events.py`.
- Task 1.2: `api/strategy.py::run_strategy` captures `get_correlation_id()` and threads it in.

## Phase 2 — Backend: delete dead schemas + orphaned service
- Task 2.1: delete `Negotiation*`/`SocialSim*`/`Household*` schemas in `api/schemas.py` (grep-verified zero importers).
- Task 2.2: `git rm services/tenant_pool.py` (+ any test).

## Phase 3 — Frontend: remove dead API + types
- Task 3.1: prune `utils/api.ts` (`negotiations`, `socialSim`, `reports`, `marketSimulation`, dead `simulation` methods).
- Task 3.2: prune `utils/types.ts` matching types. Gate: `tsc`.

## Phase 4 — Frontend: delete dead surfaces, fix routes/links
- 4.1 rm NegotiationPage, NegotiationChat, NegotiationSimulationWorkspace, useWebSocket.
- 4.2 rm AnalysisPage, ReportGenerator, ReportList, ReportViewer.
- 4.3 rm SimulationPage, MarketSimulationWorkspace, PersonaBuilder; classify+rm SimulationVisualizePage.
- 4.4 App.tsx: remove lazy imports/routes/navlinks for /negotiate,/analysis,/simulation,/simulation/visualize; keep /simulate.
- 4.5 repoint /negotiate CTAs (SearchDrawer, ResultsComparison, SimulateReportPage+test) → /portfolio.
- 4.6 clean dead calls in DashboardPage, UserProfilePage, DashboardMap → empty-state + Portfolio link.

## Phase 5 — Rebrand Overview → Analysis
- 5.1 rename OverviewTab→AnalysisTab (+test); PortfolioPage TabKey/label/testid/default.

## Phase 6 — Absorb Strategy → free-text Simulation tab
- 6.1 rename StrategyTab→SimulationTab (+test); testids/classnames strategy-*→simulation-*.
- 6.2 enrich projection table (projected NOI, cash flow, recommendation).
- 6.3 PortfolioPage wire TabKey 'strategy'→'simulation', label, render.

## Phase 7 — Verification
- 7.1 `pytest tests/ -v`; `npm run test`; `tsc`/build; update CLAUDE.md tab list + page count.

## Migration impact
None — tables already dropped by `f9a1b2c3d4e5`; only Pydantic/frontend deletions + revived event writer.
