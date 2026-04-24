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

Short-term mapping from existing code:

- `db/models.py`
  Holds the beginning of the actor and decision state.
- `services/social_simulator.py`
  Should evolve into part of the reaction engine, not remain a standalone loop.
- `agent/negotiation_engine.py`
  Should become one decision runtime over shared upstream state.
- `services/social_report_bridge.py`
  Should become part of a broader report projection layer.
- `api/social_simulation.py`
  Should expose reaction-run, replay, and projection endpoints.
- `api/negotiations.py`
  Should expose a decision-session view backed by shared knowledge state.

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

### Phase A: Canonical Taxonomy

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

### Phase B: Market-State Foundation

Build the real spatial market layer:

- neighborhood and parcel context
- market shock inputs
- zoning, transit, school, hazard, and comp signals

### Phase C: Actor And Cohort Memory

Expand household modeling into reusable actor state:

- buyer, seller, renter, investor, broker, city, and business cohorts
- structured pressure, trust, and narrative-susceptibility variables

### Phase D: Reaction Runtime

Transform the current social-sim engine into a reaction engine:

- structured reaction variables
- event propagation
- narrative extraction
- convergence and divergence tracking

### Phase E: Decision Runtime

Move transaction logic onto the shared state:

- negotiation sessions
- pricing and listing decisions
- leasing and churn behavior
- development and policy resistance

### Phase F: Outcome Projections

Store and expose:

- price movement
- offer behavior
- permit friction
- time-on-market
- neighborhood-level sentiment

### Phase G: Reports And Replay

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
