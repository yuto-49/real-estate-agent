> ℹ️ **Partly historical (2026-06).** The negotiation / social-simulation framing in
> this doc describes features that were **removed** (migration `f9a1b2c3d4e5`). The
> **layered domain runtime** it proposed, however, was built and **survives** under
> `domain/` (market → actor → reaction → decision → outcome → report) and now powers
> the investor analytics surface. Read this for the layered-runtime rationale; see
> `CLAUDE.md` and `architecture.md` for the current system.

# Layered Market Knowledge System

This document reframes negotiation and social simulation as one part of a deeper
real-estate knowledge system. Instead of treating social simulation as a
sidecar that produces a report, the platform should treat market state,
household behavior, narrative shifts, transaction decisions, and outcome
metrics as one stacked system.

It supersedes the narrower idea of "social simulation feeds a report which
feeds negotiation" as the primary architectural concept.

---

## 1. Core Thesis

Real-estate prices do not move only because of fundamentals. They also move
because of interpreted social signals.

The platform should therefore model five connected layers:

1. Spatial market layer
   Parcels, neighborhoods, zoning, transit, hazards, rents, comps, permits,
   demographics, schools, crime, and operating constraints.
2. Household and actor layer
   Buyers, renters, sellers, landlords, brokers, investors, city officials,
   local businesses, and organized community groups.
3. Social reaction layer
   Fear, hype, trust, perceived safety, school reputation, displacement
   anxiety, policy support, political resistance, and neighborhood narratives.
4. Decision layer
   Move, buy, wait, rent, list, protest, overbid, lower price, delay approval,
   raise concessions, approve permits, or hold inventory.
5. Market outcome layer
   Price changes, time-on-market, offer volume, concession rates, turnover,
   rent changes, absorption, permit friction, and neighborhood sentiment.

---

## 2. Distributed-System Analogy

The system should be reasoned about like a distributed system:

| Knowledge Layer | Distributed-System Role | Purpose |
|---|---|---|
| Spatial market layer | State store / database | Canonical world state and constraints |
| Household and actor layer | Independent services | Actors with local memory, incentives, and policies |
| Social reaction layer | Message bus | Narrative propagation, shocks, rumor flow, feedback loops |
| Decision layer | Business logic | Policy and behavior rules that transform state into actions |
| Market outcome layer | Observability / metrics | What the rest of the system and users can observe |

This framing matters because the platform should not rely on one giant prompt
to produce market behavior. It should treat each step as a state transition
with explicit causality.

---

## 3. What Changes In This Project

### 3.1 Negotiation Is No Longer The Center

Negotiation stays important, but it becomes a consumer of upstream knowledge:

- The negotiation engine consumes current market state, actor state,
  narrative state, and decision policies.
- Social simulation becomes one producer of reaction and decision signals, not
  the only "intelligence" source.
- MiroFish reports become one presentation layer over the deeper system state.

### 3.2 Social Simulation Is Broadened

The current social simulation concept focuses on household opinion rounds.
That is useful, but too narrow for the long-term product.

The broader system should model:

- localized market context
- stakeholder networks
- event-driven narrative shifts
- policy and permitting reactions
- transaction behavior under narrative pressure
- downstream pricing and absorption effects

### 3.3 Reports Become Derived Artifacts

`MiroFishReport` should be treated as a derived artifact, not the system of
record.

Reports should be generated from snapshots of:

- spatial market state
- actor cohort state
- narrative state
- decision traces
- outcome metrics

That keeps reports explainable and replayable.

---

## 4. State Model

### 4.1 Spatial Market Layer

Canonical entities:

- parcels and properties
- neighborhoods and custom market clusters
- zoning overlays and permit constraints
- transit access and mobility scores
- hazards and insurance pressure
- rents, sales comps, tax context, vacancy, and inventory
- schools, crime, amenities, employer access, and demographic composition

Suggested responsibility:

- store slow-moving market facts and regularly refreshed market indicators
- expose event emitters for changes like zoning, transit, incidents, school
  changes, financing shocks, and major openings

### 4.2 Household and Actor Layer

Canonical entities:

- household profiles
- seller profiles
- broker profiles
- investor profiles
- developer and city-actor profiles
- local business and organizer proxies

Core state variables:

- affordability pressure
- trust in neighborhood trajectory
- perceived safety
- social proof sensitivity
- displacement concern
- investor optimism
- willingness to transact
- resistance to development

### 4.3 Social Reaction Layer

Reaction state should not be vague free text only. It should be structured.

For each actor or cohort:

- maintain reaction variables as numeric or categorical state
- attach narrative snippets for explainability
- propagate updates through explicit events

Examples of reaction events:

- zoning announcement
- new transit stop
- school rating change
- crime incident
- eviction news
- viral post
- neighborhood protest
- celebrity or business endorsement
- financing rate shock

### 4.4 Decision Layer

Behavior should be modeled as explicit rules plus agent reasoning:

- rule gates for affordability, policy, timing, and role permissions
- agent reasoning for subjective tradeoffs and narrative interpretation
- explicit transition records for each decision

Examples:

- if optimism rises and affordability remains acceptable, buyer demand increases
- if displacement concern rises, resistance and permit friction increase
- if safety falls, time-on-market and concessions increase
- if hype rises among investors but not residents, speculative spread widens

### 4.5 Market Outcome Layer

Observed outputs:

- pricing and comp shifts
- time-on-market
- offer aggression and contingency behavior
- leasing conversion and churn
- public resistance and hearing friction
- neighborhood-level sentiment and narrative spread

These should be queryable as metrics, not buried in transcripts.

---

## 5. Real-Estate Workflows This Enables

### 5.1 Pre-Development Analysis

Before launching a project, simulate how residents, buyers, officials, and
businesses may react to:

- new transit
- rezoning
- luxury development
- affordable housing
- safety incidents
- school changes

The goal is not only "can this be built?" but "how does sentiment move and how
does that affect demand, approvals, and risk?"

### 5.2 Investment Underwriting

Social reaction becomes a risk-adjusted demand forecast.

Questions the system should answer:

- Will backlash delay approvals?
- Will perceived gentrification raise political risk?
- Will positive buzz lift traffic and willingness to pay?
- Will distrust suppress conversion faster than fundamentals suggest?

### 5.3 Pricing and Listing Strategy

Listings do not sell in a vacuum. Social context affects:

- who shows up
- what objections they believe
- their urgency
- their willingness to waive contingencies
- the story they tell themselves about the area

### 5.4 Broker Strategy

Brokers should be able to ask:

- which buyer personas to target
- which objections are likely to appear
- which narrative to lead with: safety, schools, transit, upside, or lifestyle
- whether to list now or hold

### 5.5 Policy and Community Engagement

Developers and cities should be able to model:

- where resistance is likely
- which narratives are driving that resistance
- what mitigation or messaging changes the trajectory

---

## 6. Recommended Build Composition

The strongest long-term stack for this repo is not one framework alone.
Use a layered composition:

| Concern | Recommended Role |
|---|---|
| Core state transitions and repeatable simulation loops | Mesa-style engine |
| Rich actor memory, belief updates, and conversation | Concordia / generative-agents style memory |
| Urban context and city-scale environment modeling | AgentSociety-style environment layer |
| Housing-specific demand, displacement, and gentrification logic | Domain ABM layer inspired by housing and gentrification repos |
| Product interface | Map, timeline, replay, scenario controls, and report views |

This means:

- Mesa or a Mesa-like internal engine should own repeatable step logic
- richer agent memory should sit on top, not replace deterministic state
- housing-specific market logic should be its own domain module
- reports and negotiation are downstream consumers of the knowledge layers

---

## 7. Proposed Project Restructure

The current repo is organized around APIs and services. That is fine for now,
but the long-term direction should move toward explicit domain modules.

Suggested target shape:

```text
domain/
  market/
    models.py
    events.py
    policies.py
    projections.py
  actors/
    profiles.py
    memory.py
    cohorts.py
    incentives.py
  reactions/
    models.py
    propagation.py
    narratives.py
    shocks.py
  decisions/
    rules.py
    negotiation.py
    pricing.py
    policy.py
  outcomes/
    metrics.py
    settlement.py
    forecasting.py

services/
  knowledge_runtime/
  report_projection/
  scenario_execution/
  replay/
```

Short-term, the existing `services/`, `agent/`, and `api/` layout can stay in
place, but new work should follow this domain split logically even before the
filesystem fully changes.

---

## 8. Migration Path From Current State

### Phase 0: Canonical Event Taxonomy

Unify event types around market, actor, reaction, decision, and outcome
domains.

Examples:

- `market.zoning_changed`
- `market.transit_opened`
- `actor.household_pressure_changed`
- `reaction.narrative_shifted`
- `decision.offer_submitted`
- `decision.listing_delayed`
- `outcome.time_on_market_updated`

### Phase 1: Market State Foundation

Strengthen the spatial market layer so it is a real state store, not only
property rows plus comps.

### Phase 2: Actor Memory And Cohort State

Expand household simulation into actor memory, pressure, trust, and narrative
susceptibility models.

### Phase 3: Reaction Engine

Turn "social sim" into an event-driven reaction engine with structured
reaction variables plus narrative summaries.

### Phase 4: Decision Projections

Move negotiation, listing, leasing, policy, and acquisition decisions onto the
shared decision layer.

### Phase 5: Outcome Projections

Expose outcome metrics as first-class projections for dashboards, reports, and
replay.

### Phase 6: Report And UI Refactor

Treat MiroFish reports, negotiation views, and scenario pages as product
interfaces over the shared knowledge system.

---

## 9. Immediate Repo-Level Implications

The next implementation wave should prioritize:

1. Define canonical layer boundaries in code and docs.
2. Refactor social simulation docs away from a single-purpose swarm plan.
3. Treat negotiation session state as one decision stream inside the broader
   knowledge runtime.
4. Introduce explicit reaction variables and market shock events before adding
   more UI complexity.
5. Rework reports so they are generated from system snapshots and projections,
   not isolated pipelines.

---

## 10. Structural Decision For The Next Milestone

Decision:
keep the layered knowledge runtime inside the current FastAPI application for
the next milestone.

This means the next phase should:

- keep domain runtime modules in-process
- keep the current FastAPI app as the API, orchestration, and projection host
- use internal module boundaries and canonical event taxonomies before adding a
  network boundary
- defer service extraction until the layered runtime and projection contracts
  are stable

Implications:

- favor `domain/` and `services/knowledge_runtime/` style internal modules
  before creating a second deployable service
- use the existing database and event infrastructure as the primary integration
  surface
- optimize for correctness, replayability, and schema clarity before
  introducing distributed transport concerns
