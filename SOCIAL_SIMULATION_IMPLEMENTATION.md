> ⚠️ **DEPRECATED / HISTORICAL (2026-06).** This roadmap describes the
> negotiation chat and social-sentiment simulation that have since been
> **removed** from the platform (Alembic migration `f9a1b2c3d4e5` dropped the
> backing tables; the frontend surface and dead schemas were removed
> afterward). It is retained for historical context only. The **layered domain
> runtime** and **market-signal pipeline** it seeded survive and now power the
> investor analytics surface — see `CLAUDE.md` and `architecture.md` for the
> current system.

# Social Simulation + Market Knowledge System Roadmap

This file is the current implementation roadmap for negotiation and social
simulation work.

It replaces the older, narrower plan that treated social simulation mainly as
"household opinion rounds that generate a report." The project direction is now
to build a deeper market knowledge system where negotiation, reports, and
social simulation are downstream consumers of shared layered state.

Source-of-truth architecture document:
[doc/layered-market-knowledge-system.md](doc/layered-market-knowledge-system.md)

---

## 1. New Planning Frame

The system should be built as five linked layers:

1. Spatial market layer
2. Household and actor layer
3. Social reaction layer
4. Decision layer
5. Market outcome layer

This means:

- social simulation is not a separate product island
- negotiation is not the architectural center
- reports are derived artifacts, not the source of truth
- the platform should evolve toward a replayable knowledge runtime

---

## 2. What The Previous Plan Missed

The previous implementation plan was useful for getting a first runnable
version, but it was still too local.

It focused on:

- household graph construction
- opinion rounds
- a report bridge
- report-seeded negotiation

It did not fully define:

- a canonical market-state layer
- actor memory beyond household sentiment
- a proper reaction-event model
- decision projections outside negotiation
- observable market outcome projections
- how policy, permitting, development, leasing, and sales all connect

---

## 3. Revised Architecture Direction

### 3.1 Spatial Market Layer

Add or strengthen canonical state for:

- parcel and property context
- neighborhood clusters
- zoning and permit context
- transit and accessibility
- schools, safety, amenities, and hazards
- rent, vacancy, turnover, comps, and absorption

This is the state store that other layers read from.

### 3.2 Household And Actor Layer

Model distinct actor types, not just synthetic households:

- buyers
- renters
- sellers
- landlords
- brokers
- investors
- city officials
- local businesses and organized groups

Each actor or cohort should have structured variables such as:

- affordability pressure
- trust in neighborhood trajectory
- perceived safety
- social proof
- displacement concern
- investor optimism
- willingness to transact
- resistance to development

### 3.3 Social Reaction Layer

Reactions must be stateful and event-driven, not only free-form narratives.

Reaction events include:

- zoning announcements
- transit changes
- school changes
- eviction news
- crime incidents
- viral posts
- protests
- endorsements
- rate shocks

The reaction layer should update structured reaction variables and attach
explainable narrative summaries.

### 3.4 Decision Layer

Decisions should be projections over state plus rules plus agent reasoning.

Examples:

- buy now vs wait
- list now vs hold
- overbid vs seek concessions
- protest vs support
- approve vs resist development
- lease, renew, churn, or move

Negotiation becomes one decision stream within this layer.

### 3.5 Outcome Layer

The system should project and store observable outcomes like:

- time-on-market
- offer count and aggressiveness
- concessions
- turnover
- permit friction
- pricing movement
- neighborhood sentiment

These outcomes should drive dashboards and reports.

---

## 4. Current Repo Mapping

Status as of 2026-05-07 — Phases A–G complete, layered runtime live under `domain/`:

- `domain/events.py` — canonical event taxonomy (Phase A) ✅
- `domain/market/` — `MarketContextSnapshot` model (Phase B) ✅
- `services/market_state.py` — async snapshot builder over `MarketSignal` rows ✅
- `db/models.py::MarketSignal` — single new table; migration `e1f8a9c4d572` ✅
- `domain/actors/` — `ActorSignalState`, `CohortSignalState`, `ActorType` (Phase C) ✅
- `domain/reactions/` — `ReactionEngine`, narrative clustering, convergence (Phase D) ✅
- `domain/decisions/` — `DecisionRuntime` + 5 built-in policies (Phase E) ✅
- `domain/outcomes/` — outcome builders + `build_outcome_snapshot()` (Phase F) ✅
- `domain/reports/` — underwriting / negotiation / policy briefs + replay (Phase G) ✅

Untouched legacy components — additive, not replaced:

- `services/social_simulator.py` — original opinion-round loop still drives
  `/api/social-sim/*`. Long-term: delegate state-folding to `ReactionEngine`,
  but no migration scheduled.
- `agent/negotiation_engine.py` — live negotiation orchestration. The new
  `NegotiationPolicy` in `domain/decisions/policies.py` wraps
  `domain.decisions.negotiation` helpers without coupling to this engine.
- `services/social_report_bridge.py` — still produces MiroFish-compatible
  payloads. New report builders in `domain/reports/` are additive.
- `api/social_simulation.py`, `api/negotiations.py` — unchanged. Future work:
  expose reaction-replay and decision-runtime read-models behind these routes.

---

## 5. Updated Build Strategy

Recommended composition:

1. Mesa-style state engine for deterministic rounds and projections.
2. Concordia or generative-agents style memory for deeper actor context.
3. AgentSociety-style environment modeling for urban and community context.
4. Housing ABM and gentrification-style logic for domain-specific rules.
5. Map, replay, report, and scenario UI as interface layers over the runtime.

This is intentionally stacked. No single framework should own the full system.

---

## 6. Revised Execution Plan

> **Status:** Phases A–G complete as of 2026-05-07. 458 tests passing,
> 96 net-new across the seven phases, no regressions, single new DB table
> (`market_signals`). All deliverables landed under `domain/` as pure-Python
> projections. See section 10 for what's now buildable on top.

### Phase A: Canonical Taxonomy ✅ Complete

Define the domain vocabulary and event taxonomy:

- `market.*`
- `actor.*`
- `reaction.*`
- `decision.*`
- `outcome.*`

This should drive:

- domain events
- websocket projections
- report generation
- replay tooling

### Phase B: Market-State Foundation ✅ Complete

Build the real spatial market layer:

- neighborhood and parcel context
- market shock inputs
- zoning, transit, school, hazard, and comp signals

### Phase C: Actor And Cohort Memory ✅ Complete

Expand household modeling into reusable actor state:

- buyer, seller, renter, investor, broker, city, and business cohorts
- structured pressure, trust, and narrative-susceptibility variables

### Phase D: Reaction Runtime ✅ Complete

Transform the current social-sim engine into a reaction engine:

- structured reaction variables
- event propagation
- narrative extraction
- convergence and divergence tracking

### Phase E: Decision Runtime ✅ Complete

Move transaction logic onto the shared state:

- negotiation sessions
- pricing and listing decisions
- leasing and churn behavior
- development and policy resistance

### Phase F: Outcome Projections ✅ Complete

Store and expose:

- price movement
- offer behavior
- permit friction
- time-on-market
- neighborhood-level sentiment

### Phase G: Reports And Replay ✅ Complete

Generate MiroFish-style artifacts as projections from the layered runtime:

- underwriting reports
- negotiation briefings
- policy/community risk briefs
- scenario replay narratives

---

## 7. Immediate Implementation Priorities

The next concrete engineering steps should be:

1. Add canonical event namespaces for market, actor, reaction, decision, and
   outcome transitions.
2. Refactor social-sim state so it clearly represents reaction variables and
   narrative propagation, not just household round logs.
3. Define snapshot builders that can generate reports from layered state.
4. Keep the negotiation session API, but reposition it as one decision-layer
   consumer.
5. Delay UI expansion until the reaction and decision layer boundaries are
   explicit in code.

---

## 7.5 Frontend Surface — Persona Risk Workspace

The `/negotiate` route in the React app has been repositioned. It is no
longer "agent chat for negotiation"; it is the **persona risk workspace**
where users run social simulations to project how different households will
move under a trigger event.

Concrete shape (current code in `frontend/src/pages/NegotiationPage.tsx`):

- **Inputs:** trigger user, zip code, income band (low / moderate / middle /
  upper), max rounds, topic selection (price, displacement, gentrification,
  transit, school, eviction risk, ...).
- **Live output during the run:** status counter, current round, action
  count, per-round household actions (round_num, topic, action_type,
  sentiment_value, narrative), topic timeline (dominant stance + average
  sentiment per round).
- **Terminal output:** narrative_output and sentiment_delta JSON, ready to
  feed `services/social_report_bridge.py` for a MiroFish-style report.

The legacy negotiation session machinery (Session Setup, Session State,
Typed Actions, Offer History, Event Replay, Live WebSocket Feed) is still
embedded in the same page for downstream consumers, but the social-sim
panel is the primary workspace.

**Implication:** further UI work on persona-risk visualization (cohort
heatmaps, comparative scenario runs, sensitivity sliders) should land on
this route, not a new one.

## 8. What Stays Valid From The Current Build

The recent work is still useful and does not need to be discarded:

- negotiation session read model
- negotiation-scoped offer ledger
- websocket event streaming
- social simulation run lifecycle
- report generation guardrails

Those pieces should be treated as transitional infrastructure for the deeper
knowledge system.

---

## 9. Structural Decision For The Next Phase

Decision:
keep the layered knowledge runtime inside the current FastAPI app for the next
milestone.

Execution consequences:

1. Build the next layer boundaries as internal modules first, not separate
   services.
2. Keep FastAPI as the host for APIs, orchestration, projections, and runtime
   coordination.
3. Use domain events and shared persistence contracts as the primary seams.
4. Postpone network service extraction until the reaction, decision, and
   outcome layers have stable contracts.

This keeps the next milestone focused on model quality, event taxonomy, and
replayable behavior instead of early distributed-systems overhead.

---

## 10. Lean Choices Held (Phases A–G)

The implementation deliberately favored additive primitives over rewrites.
Every cross-cutting choice below applied to all seven phases unless noted:

**Cross-cutting:**
- All new code lives under `domain/`. Existing `services/`, `agent/`, `api/`,
  and `db/` modules are untouched (one exception: `db/models.py` gained
  `MarketSignal` for Phase B).
- Single new DB table (`market_signals`, migration `e1f8a9c4d572`). No
  schema changes for Phases C–G.
- All builders and runtimes are pure-Python with frozen `slots=True`
  dataclasses — deterministic, side-effect free, no async.
- **Lenient validation**: missing or unknown inputs log a warning and yield
  a sensible default (`None`, neutral score, empty tuple). `ValueError` is
  reserved for real state-machine transitions (`domain.decisions.negotiation`).
- Tests use the existing in-memory SQLite + fakeredis convention. No
  external services required.

**Per-phase:**
| Phase | Specific lean choices |
|---|---|
| A — Event taxonomy | Lenient registry (1b), strings not enums (2a), central catalog (3a), no migration of existing emit sites (4a), no Pydantic payload schemas (5a) |
| B — Market state | New table only — no refactor of `properties` or `neighborhoods`. Property-level signals win, neighborhood signals only gap-fill. Idempotent migration. No caching layer. |
| C — Actor / cohort | Reused 8-pressure `ActorSignalState` shape. Defensive read of `actor_type` / `role` / `housing_type`. No persistence — projections derive from existing `UserProfile`/household models. |
| D — Reaction runtime | In-memory `dict[str, ReactionVector]`. `services/social_simulator.py` left running. Mean per-variable variance vs. configurable threshold (no scipy). |
| E — Decision runtime | `agent/negotiation_engine.py` untouched — `NegotiationPolicy` wraps `domain.decisions.negotiation`. Stateless across calls. Explicit policy registration, no auto-discovery. Per-policy exception isolation. |
| F — Outcome projections | Existing `MarketOutcomeSnapshot` shape filled in, not changed. `project_negotiation_session` left alone. No persistence. Naive datetimes auto-coerced to UTC. |
| G — Reports / replay | `MiroFishReportData` and `MiroFishReport` DB model untouched. Replay is in-memory — no event-store dependency. Neutral defaults instead of raises. |

---

## 11. What's Now Buildable On The Spec

With the layered runtime in place, the next milestones become small and
mechanical — most of the new work is wiring, persistence, and UI on top of
existing pure functions. Roughly in priority order:

1. **Wire `DecisionRuntime` into the orchestrator.** Build a
   `DecisionContext` per request from `services/market_state.build_snapshot`
   plus the live reaction state, run `default_policies()`, surface
   recommendations alongside existing tool calls. No new domain code needed.
2. **Persist outcome snapshots.** New `outcome_snapshots` table writing
   `MarketOutcomeSnapshot` per listing/closed deal. Read-only API at
   `GET /api/listings/{id}/outcome` returning the latest projection.
3. **Reports API.** `POST /api/reports/underwriting`,
   `/api/reports/negotiation-briefing/{negotiation_id}`,
   `/api/reports/policy-risk` — each one builds a context, calls the
   matching `domain.reports.builders.*`, returns the frozen artifact as JSON.
4. **WebSocket replay streaming.** Stream `ReplayFrame`s as the reaction
   engine processes events, keyed off `correlation_id`. `replay_reactions`
   is already pure — only the transport is missing.
5. **Backfill `MarketSignal` from existing data sources.** Zoning, permit
   rate, transit score, school score, hazard flags. One-shot scripts under
   `scripts/`; no domain changes.
6. **Connect the legacy social simulator to `ReactionEngine`.** Delegate
   per-round state folding to `engine.apply_batch()`, keep the LLM-driven
   opinion generation. Convergence detection moves to `engine.convergence()`.
7. **Persist `DecisionRecommendation` history per negotiation.** New
   `decision_log` table. Lets us audit which policy fired when.
8. **Frontend dashboards.** Render `MarketOutcomeSnapshot` per listing,
   decision-runtime recommendations on the negotiation page, replay
   timelines from `ReplayNarrative.frames`.
9. **Cohort views.** Run `cohort_signals()` over user/household snapshots,
   expose cohort heatmaps in the UI.
10. **Scenario playground.** Pre-built `ReactionEvent` streams (rent shock,
    transit announcement, eviction wave) → `replay_reactions()` → render
    via existing replay UI. Pure read-only feature.

None of these require new core algorithms — the projections already exist
and are tested. Each item is essentially a persistence + transport task.
