# Social Behavior Simulation — Implementation Plan

## Context & Goal

Layer a **swarm social simulation** on top of the existing synthetic household population to generate
**personalized housing reports**. Before a user's negotiation simulation runs, a social behavior
simulation models how households like theirs form opinions about housing markets, policies, and
neighborhoods. The evolved opinions and narratives become the intelligence that seeds the
`MiroFishReport` — replacing or augmenting the mock MiroFish client with ground-truth simulated
community sentiment.

```
Synthetic Households (100)
        ↓
  Social Graph (edges = proximity, income, demographics)
        ↓
  Behavior Simulation (opinion spreading, narrative evolution — N rounds)
        ↓
  Report Assembly (SimulationNarrative → MiroFishReport.report_json)
        ↓
  Negotiation Simulation (buyer/seller/broker agents read briefings from report)
        ↓
  Personalized Deal Outcome
```

---

## What the Current Plan Is Missing

The Synthetic Household Population plan (model + seed + API) creates a **static dataset**. It has no:

1. **Social graph** — no edges between households, so opinions can't spread
2. **Opinion/stance state** — no field on HouseholdProfile to hold current beliefs
3. **Simulation loop** — no engine to advance rounds of behavior
4. **Narrative accumulation** — no structure to record what emerged from each round
5. **Report bridge** — no link from social simulation output → `MiroFishReport.report_json`
6. **Persona depth** — each household needs communication style + influence weight for realistic dynamics

---

## Improved Architecture

### Layer 0 — Household Foundation (from existing plan, with additions)

Additions to `HouseholdProfile` beyond the original plan:

```python
# Opinion & Social fields — add to HouseholdProfile in db/models.py
housing_market_sentiment   : Float      # -1.0 (bearish) to +1.0 (bullish)  default 0.0
policy_support_score       : Float      # -1.0 (opposed) to +1.0 (supportive) default 0.0
neighborhood_satisfaction  : Float      # 0.0 to 1.0
influence_weight           : Float      # how much this household sways neighbors (0.1–1.0)
communication_style        : String     # "vocal", "passive", "analytical", "emotional"
social_connections         : Integer    # number of edges in social graph
opinion_stability          : Float      # resistance to opinion change (0=volatile, 1=rigid)
```

---

### Layer 1 — Social Graph

**New file: `db/models.py` additions**

```python
class HouseholdSocialEdge(Base):
    __tablename__ = "household_social_edges"

    id              = Column(UUID, primary_key=True, default=uuid4)
    source_id       = Column(UUID, ForeignKey("household_profiles.id"))
    target_id       = Column(UUID, ForeignKey("household_profiles.id"))
    edge_weight     = Column(Float)          # 0.0–1.0 (strength of influence)
    edge_type       = Column(String)         # "neighbor", "income_peer", "language_peer", "demographic"
    created_at      = Column(DateTime)

    source = relationship("HouseholdProfile", foreign_keys=[source_id])
    target = relationship("HouseholdProfile", foreign_keys=[target_id])
```

**Graph construction rules (in seed script):**
- `neighbor`: same zip_code → edge_weight 0.6–0.9
- `income_peer`: same income_band → edge_weight 0.3–0.6
- `language_peer`: same primary_language (non-English) → edge_weight 0.5–0.8
- `demographic`: similar household_size + num_children → edge_weight 0.2–0.4
- Cap each household at 8–12 edges to keep density realistic

---

### Layer 2 — Opinion & Narrative Models

**New file: `db/models.py` additions**

```python
class SocialSimulationRun(Base):
    __tablename__ = "social_simulation_runs"

    id              = Column(UUID, primary_key=True)
    trigger_user_id = Column(UUID, ForeignKey("user_profiles.id"))  # who triggered it
    household_filter= Column(JSONB)   # which households were included (zip, income_band, etc.)
    total_rounds    = Column(Integer)
    status          = Column(String)  # preparing | running | completed | failed
    narrative_output= Column(JSONB)   # final evolved narratives per topic
    sentiment_delta = Column(JSONB)   # how opinions shifted across rounds
    report_id       = Column(UUID, ForeignKey("mirofish_reports.id"), nullable=True)
    created_at      = Column(DateTime)
    completed_at    = Column(DateTime, nullable=True)


class SocialSimulationAction(Base):
    __tablename__ = "social_simulation_actions"

    id              = Column(UUID, primary_key=True)
    run_id          = Column(UUID, ForeignKey("social_simulation_runs.id"))
    round_num       = Column(Integer)
    household_id    = Column(UUID, ForeignKey("household_profiles.id"))
    action_type     = Column(String)   # "post_opinion", "share_narrative", "update_stance", "go_silent"
    topic           = Column(String)   # "market_prices", "eviction_policy", "voucher_program", "neighborhood"
    content         = Column(Text)     # LLM-generated opinion text
    sentiment_value = Column(Float)    # resulting sentiment after this action
    influenced_by   = Column(JSONB)    # list of household_ids that swayed this action
    created_at      = Column(DateTime)
```

---

### Layer 3 — Social Simulation Engine

**New file: `services/social_simulator.py`**

```
SocialSimulator
├── __init__(run_id, households, edges, config)
│     ├── load HouseholdProfile records + social graph
│     ├── initialize opinion state per household
│     └── set topics: ["market_prices", "eviction_policy", "voucher_program", "neighborhood_safety"]
│
├── run() → SocialSimulationResult
│     For round in 1..total_rounds:
│       1. Select active households (weighted by influence_weight + communication_style)
│       2. For each active household:
│            a. Gather neighbor opinions via social edges
│            b. Call Claude with household context + neighbor opinions → generate stance update + action
│            c. Apply opinion drift formula:
│               new_opinion = (stability * current) + ((1-stability) * weighted_neighbor_avg) + LLM_delta
│            d. Write SocialSimulationAction to DB
│       3. Detect narrative clusters (households with similar opinions grouping)
│       4. Check convergence — if avg opinion delta < 0.02, stop early
│
├── _build_household_prompt(household, neighbors, round_num) → str
│     Include: income context, housing stress, neighborhood, current opinion,
│              neighbor stances (anonymized), current round event (if any)
│
├── _apply_opinion_drift(household, llm_delta, neighbor_opinions) → float
│     Formula: weighted average with stability as resistance factor
│
├── _detect_narratives() → List[Narrative]
│     Cluster households by opinion similarity → extract dominant narratives per topic
│
└── _build_report_payload() → dict
      Translate simulation output → MiroFishReport-compatible report_json structure
      Map: market sentiment cluster → market_outlook
           eviction_policy stance → risk_factors
           voucher_program support → opportunity_indicators
           neighborhood_safety narrative → neighborhood_score
```

**Concurrency:** `asyncio.Semaphore(5)` — max 5 households processed per round concurrently.
**Round design:** 8–15 rounds is sufficient for opinion convergence in a 100-node graph.

---

### Layer 4 — Report Bridge

**New file: `services/social_report_bridge.py`**

This translates `SocialSimulationRun.narrative_output` → `MiroFishReport.report_json` format,
so the existing negotiation simulator can consume it unchanged via `_build_intelligence_briefings()`.

```python
def build_report_from_social_sim(
    run: SocialSimulationRun,
    target_household: HouseholdProfile,
    property_data: dict
) -> dict:
    """
    Returns a dict shaped like MiroFishReport.report_json so the existing
    negotiation simulator intelligence briefing system works without modification.
    """
    return {
        "market_analysis": {
            "trend": derive_trend(run.sentiment_delta["market_prices"]),
            "confidence": run.narrative_output["market_prices"]["consensus_strength"],
            "health_score": map_sentiment_to_score(run.narrative_output),
            "appreciation_forecast": ...,
        },
        "risk_assessment": {
            "probability_of_loss": derive_risk(run, target_household),
            "key_risks": extract_risk_narratives(run, target_household),
            "eviction_risk_context": run.narrative_output["eviction_policy"],
        },
        "comparable_analysis": { ... },     # from property_data
        "decision_framework": {
            "strategies": derive_strategies(run, target_household),
            "timing_recommendation": ...,
            "community_sentiment_summary": run.narrative_output,
        },
        "household_context": {              # NEW — personalized section
            "income_band": target_household.income_band,
            "eviction_risk": target_household.eviction_risk,
            "voucher_eligible": target_household.has_housing_voucher,
            "peer_sentiment": get_peer_group_opinion(run, target_household),
            "neighborhood_narrative": run.narrative_output["neighborhood_safety"],
        }
    }
```

---

### Layer 5 — API Endpoints

**New file: `api/social_simulation.py`**

```
POST /api/social-sim/start
     Body: { user_id, zip_code?, income_band?, max_rounds? }
     → Creates SocialSimulationRun, enqueues background task
     → Returns { run_id, status }

GET  /api/social-sim/{run_id}/status
     → Returns { status, current_round, total_rounds, action_count }

GET  /api/social-sim/{run_id}/result
     → Returns { narrative_output, sentiment_delta, final_opinions }

GET  /api/social-sim/{run_id}/actions
     → Paginated action log (round_num, household_id, topic, content, sentiment_value)

GET  /api/social-sim/{run_id}/timeline
     → Round-by-round opinion trajectory (mirrors MiroFish SimulationRunner.get_timeline())

POST /api/social-sim/{run_id}/generate-report
     Body: { property_id, household_id }
     → Calls social_report_bridge.build_report_from_social_sim()
     → Saves as MiroFishReport record
     → Returns { report_id }  ← this report_id feeds directly into POST /api/simulation/start-from-report
```

**Register in `main.py`:**
```python
app.include_router(social_sim_router, prefix="/api/social-sim", tags=["social-simulation"])
```

---

### Layer 6 — Seed Script Additions

**Additions to `scripts/seed_households.py`** (beyond original plan):

```python
# After creating 100 HouseholdProfiles:

# 1. Assign opinion fields with income-correlated initialization
#    - Low income → bearish market sentiment, higher policy support
#    - High income → bullish market sentiment, lower policy support

# 2. Build social graph edges
build_social_graph(households, session)
#    Rules:
#    - Same zip → neighbor edges (weight 0.7)
#    - Same income_band → peer edges (weight 0.4)
#    - Same language (non-English) → language edges (weight 0.6)
#    - Similar household_size (±1) → demographic edges (weight 0.3)
#    - Max 10 edges per household

# 3. Assign influence_weight based on communication_style:
#    vocal: 0.7–1.0 | analytical: 0.5–0.8 | passive: 0.1–0.3 | emotional: 0.4–0.7
```

---

## Complete File Change List

### New Files
| File | Purpose |
|------|---------|
| `services/social_simulator.py` | Core simulation engine (opinion rounds, narrative clustering) |
| `services/social_report_bridge.py` | Translate simulation output → MiroFishReport format |
| `api/social_simulation.py` | REST endpoints for social sim lifecycle |
| `scripts/seed_households.py` | Seed 100 households + social graph (from original plan + additions) |

### Modified Files
| File | Change |
|------|--------|
| `db/models.py` | Add `HouseholdProfile`, `HouseholdSocialEdge`, `SocialSimulationRun`, `SocialSimulationAction` + opinion fields |
| `api/schemas.py` | Add `HouseholdResponse`, `SocialSimRunResponse`, `SocialSimResultResponse`, `SocialSimActionResponse` |
| `main.py` | Register `social_sim_router` + `households_router` |
| `alembic/versions/` | New migration for all 4 new tables |

### Unchanged (reuse as-is)
| File | Why unchanged |
|------|--------------|
| `services/negotiation_simulator.py` | Already consumes `report_json` via `_build_intelligence_briefings()` |
| `intelligence/mirofish_client.py` | Social report bridge outputs same schema — no changes needed |
| `agent/buyer_agent.py` | `get_intelligence_report` tool works unchanged |
| `services/batch_simulator.py` | Batch scenarios work on top of the generated report |

---

## Implementation Order

```
Step 1 — Data Foundation
  db/models.py: Add HouseholdProfile + opinion fields + HouseholdSocialEdge
  db/models.py: Add SocialSimulationRun + SocialSimulationAction
  api/schemas.py: Add all new Pydantic schemas
  → alembic revision --autogenerate -m "household_social_simulation_tables"
  → alembic upgrade head

Step 2 — Seed Data
  scripts/seed_households.py: 100 households with opinion fields + social graph edges
  → python scripts/seed_households.py --count 100 --seed 42

Step 3 — Simulation Engine
  services/social_simulator.py: Full simulation loop with Claude API calls
  → Unit test: run 3 rounds on 10 households, verify opinion drift

Step 4 — Report Bridge
  services/social_report_bridge.py: Map narrative output → report_json schema
  → Integration test: generate report from completed run, pass to negotiation simulator

Step 5 — API Layer
  api/social_simulation.py: All endpoints + background task wiring
  api/households.py: Household CRUD + stats
  main.py: Register both routers

Step 6 — End-to-End Test
  POST /api/social-sim/start  { user_id: "...", zip_code: "60601" }
  GET  /api/social-sim/{run_id}/status  (poll until completed)
  POST /api/social-sim/{run_id}/generate-report  { property_id: "...", household_id: "..." }
  POST /api/simulation/start-from-report  { report_id: "...", ... }
  GET  /api/simulation/result/{sim_id}
```

---

## Why This Architecture Is Better

### 1. Reports are earned, not mocked
The current `MockMiroFishClient` generates static fictional reports. With social simulation,
the `market_outlook`, `risk_factors`, and `neighborhood_score` in the report reflect actual
simulated community behavior from demographically realistic households — making the report
meaningful for policy testing.

### 2. Personalization is structural, not prompt-engineered
The `household_context` section added to `report_json` carries the target household's peer group
opinions, eviction risk context, and voucher eligibility. The buyer agent reads this via the
existing `get_intelligence_report` tool without any changes to the agent code. Personalization
flows through data, not hardcoded prompts.

### 3. The social graph makes scenarios non-uniform
Batch simulation currently varies price/strategy across 6 fixed scenarios. With social simulation,
you can run the same negotiation against reports generated from different social contexts
(e.g., high-eviction-risk zip vs. stable-income zip) — the scenario variation becomes sociological
rather than just financial.

### 4. Opinion drift creates temporal intelligence
`sentiment_delta` in `SocialSimulationRun` captures how quickly opinions shifted during simulation.
A high delta = volatile market sentiment = maps directly to higher `probability_of_loss` in the
risk section, which the negotiation simulator already uses to cap `max_rounds` and choose
conservative strategies. The connection is automatic.

### 5. Reuses all existing infrastructure
- Same `MiroFishReport` table and schema
- Same `start-from-report` endpoint
- Same negotiation simulator `_build_intelligence_briefings()`
- Same `SimulationResult` persistence
- Same batch scenario system

The social simulation is an **upstream data source**, not a replacement. It plugs into the
existing pipeline at the report_id boundary.

---

## Household → Report → Negotiation Data Flow (Complete)

```
User requests personalized report for property X
  ↓
POST /api/social-sim/start { user_id, zip_code of property X }
  → Filters households by zip + nearby income bands
  → Runs 10 rounds of opinion simulation across matched households
  → Clusters into narratives: market_prices, eviction_policy, voucher_program, neighborhood_safety
  ↓
POST /api/social-sim/{run_id}/generate-report { property_id, household_id }
  → social_report_bridge.build_report_from_social_sim()
  → Saves MiroFishReport { report_json: { market_analysis, risk_assessment, decision_framework, household_context } }
  ↓
POST /api/simulation/start-from-report { report_id }
  → NegotiationSimulator.derive_config_from_report()   ← reads market_analysis + risk_assessment
  → NegotiationSimulator._build_intelligence_briefings() ← injects all sections into agent prompts
  → Buyer agent sees: community sentiment, peer group opinion, eviction risk context, voucher eligibility
  → Seller agent sees: neighborhood narrative, market health from simulated community
  → Broker agent sees: ZOPA estimate grounded in community data
  ↓
Negotiation runs → SimulationResult persisted
  → outcome, final_price, rounds_completed, price_path
```

---

## Key Design Constraints

- **Claude API calls per round:** max 5 concurrent (Semaphore) × active_households_per_round
  Keep `active_household_fraction = 0.3` → 30 of 100 households active per round → 6 batches
- **Round count:** 10 rounds is default; convergence check exits early if avg delta < 0.02
- **Opinion formula:** `new = (stability × current) + ((1 - stability) × peer_avg) + (0.1 × llm_delta)`
  where `llm_delta` is extracted from Claude's generated stance text (-0.5 to +0.5)
- **No IPC needed:** unlike MiroFish's subprocess model, run entirely in-process with asyncio
  (same pattern as existing `NegotiationSimulator`) — simpler, no filesystem coordination
- **DB writes per run:** ~300 `SocialSimulationAction` rows for 100 households × 10 rounds × 0.3 active rate
