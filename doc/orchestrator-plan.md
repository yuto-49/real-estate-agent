# Orchestrator Pipeline — Next-Phase Plan

> **Status:** Plan only. No code written yet.
> **Decisions baked in:** Hybrid LLM use · Ubuntu single-host runtime (Option A) · Postgres-backed run store from day one.
> **Author context:** Written for someone re-orienting to the backend. Plain-language first, file paths throughout.

---

## 0. What the app does today (orientation)

The platform answers one question for a Tokyo property investor:

> *"I have ¥X and a strategy. Which apartment should I buy, and will it still
> make money in 10 years after taxes, vacancy, and interest-rate shocks?"*

### Vocabulary (the only 6 terms that matter)

| Term | Plain meaning |
|---|---|
| **FastAPI** | The web server. Exposes endpoints (URLs the frontend calls). |
| **Router** | A file grouping related endpoints. `main.py` mounts 12 of them. |
| **Model (SQLAlchemy)** | A Python class mirroring a DB table. `Property` = one row in `properties`. |
| **Schema (Pydantic)** | The JSON shape in/out of an endpoint. Validates input at the door. |
| **Service** | Reusable business logic, no HTTP concerns. Lives in `services/`. |
| **Agent / persona** | One Claude API call with a tight job. The analyst council is 4 run in parallel. |

### Current data flow

```
1. SIGN IN          Supabase login → backend trusts a signed JWT.
2. ONBOARDING       api/onboarding.py + api/investor_profile.py
                    Budget, ward, strategy, tax bracket → investor_profiles row.
                    services/strategy_profile.py parses free text → StrategyProfile.
3. RECOMMEND        services/property_recommender.py  (deterministic, no Claude)
                    Filter by budget/ward/walk-time, score yield+risk → shortlist.
4. ANALYZE LISTING  POST /api/listings/{id}/analyze → agent/analyst_council.py
                    4 Claude personas in PARALLEL (risk / location / depreciation / vacancy)
                    → blended 0–100 score. Cost = 4 calls. Failures isolate.
5. TAX ENGINE       intelligence/depreciation_jp.py  (pure math)
                    法定耐用年数 + 簡便法 → tax-shield schedule. Persona interprets it.
6. PROJECT          services/portfolio_summary.py + strategy_runner.py (pure math)
                    DCF + Monte Carlo + depreciation + stress paths over hold horizon.
7. UNIFIED REPORT   services/unified_report.py
                    "Does the strategy survive its own projection?"
```

**Key fact:** Claude is used in exactly ONE place today — analyzing individual
listings (step 4). Everything else is deterministic math. That is why the
system is cheap to run, and it is the principle this plan preserves.

---

## 1. Target architecture (the orchestrator topology)

New code in **bold**.

```
                         POST /api/runs        (api/orchestrator.py ← NEW)
                              │
              ┌───────────────▼────────────────┐
              │   Orchestrator / Supervisor      │  agent/orchestrator.py ← NEW
              │   decomposes · delegates ·       │  (asyncio state machine,
              │   collects · ranks               │   streams progress over WS)
              └───┬───────┬───────┬─────────┬────┘
                  │       │       │         │
        ┌─────────▼──┐ ┌──▼─────────┐ ┌────▼────────┐ ┌──────────▼─────────┐
        │ Intake     │ │ Market     │ │ Discovery   │ │ Synthesis          │
        │ agent      │ │ research   │ │ agent       │ │ agent (fan-in)     │
        │ pauses for │ │ fan-out:   │ │ → N         │ │ collect N          │
        │ the human  │ │ 1 sub per  │ │ candidate   │ │ scorecards, rank,  │
        │ if a field │ │ ward       │ │ properties  │ │ write recommend.   │
        │ is missing │ │ (parallel) │ │             │ │                    │
        └────────────┘ └────────────┘ └─────┬───────┘ └──────────▲─────────┘
        intake_agent.py market_research_      │ fan-out           │
                        agent.py              │ 1 per property     │
                                              ▼                    │
                              ┌────────────────────────────────┐  │
                              │  Property-Analysis agent ×N      │──┘
                              │  = EXISTING analyst council ✅   │
                              │    agent/analyst_council.py      │
                              └────────────────────────────────┘
```

**Cost-control principle:** the orchestrator itself is plain `asyncio` glue (not
an LLM). Under the **Hybrid** decision, Claude runs only at:
- Intake (1 call to parse free text),
- each qualifying ward (1 optional *narrative* call — the deterministic signal
  read gates first; the LLM call only adds judgment),
- the per-property council (4 calls × N).

Discovery, projection, and synthesis stay 100% deterministic.

### Gap analysis — what exists vs. what's new

| Pipeline node | Status | Location |
|---|---|---|
| Intake agent | ⚠️ form only, no human-pause loop | `api/onboarding.py`, `services/strategy_profile.py` |
| Market-research agent (per-ward fan-out) | ❌ missing | (new) — reuses `services/providers_jp/`, `market_state.py` |
| Property-discovery agent | ⚠️ deterministic ranking exists | `services/property_recommender.py` |
| Fan-out: 1 analysis agent / property | ✅ **built** | `agent/analyst_council.py` |
| Fan-in: synthesis | ⚠️ partial (reconcile only) | `services/unified_report.py` |
| Orchestrator / supervisor | ❌ missing | (new) |
| Durable run store | ❌ in-memory dict only | `services/strategy_runner.py` (`_set`/`get_strategy_run`) |

---

## 2. Implementation plan (phased, TDD, 80%+ coverage)

Each phase is independently shippable and testable.

### Phase 0 — Foundation: the durable run record  (~½ day)
- **New model** `AnalysisRun` (table `analysis_runs`):
  `id`, `user_id`, `investor_profile_id`, `status`, `goal_text`,
  `result` (JSONB), `created_at`, `updated_at`.
  `status` ∈ `{intake_pending, needs_input, researching, discovering, analyzing, synthesizing, done, error}`.
- **Alembic migration** for the new table.
- **New schemas** `RunRequest` / `RunStatusResponse` in `api/schemas.py`.
- **Why durable, not in-memory:** an in-process dict (today's `strategy_runner`
  pattern) cannot be shared between the API process and a future worker
  process. Postgres-backed from the start keeps the Ubuntu-worker door open
  (see §3 Option B) and survives restarts.

### Phase 1 — Synthesis agent FIRST  (~1 day)
- **New** `services/synthesis.py`: pure function
  `rank_scorecards(profile, [ListingAnalysis], [ScoredProperty]) → Recommendation`.
  Deterministic blend of council score + recommender components + lifetime-sim
  survival flag → ranked list with reasoning strings.
- **Why first:** zero dependencies, pure math (fast tests), and it pins down the
  output contract the whole pipeline aims at.

### Phase 2 — Orchestrator skeleton + Intake  (~1–2 days)
- **New** `agent/orchestrator.py`: `async def run_analysis(run_id)` walks the
  state machine, calls each agent (sequential where dependent, `asyncio.gather`
  where parallel), writes status to `AnalysisRun` at every step. Same
  streaming pattern as `strategy_runner.execute_strategy_run`.
- **New** `agent/intake_agent.py`: wraps `strategy_profile.py`. One Claude call
  parses free text → `StrategyProfile`, then checks required fields (budget,
  tier, ward, horizon). Missing → status `needs_input`, return missing list,
  **stop**. Human answers via resume endpoint; orchestrator continues. This is
  the "pauses for the human" requirement.
- **New** `api/orchestrator.py`:
  `POST /api/runs` (start) · `GET /api/runs/{id}` (poll) ·
  `POST /api/runs/{id}/resume` (answer intake) · WS endpoint (live progress).
- Mount the router in `main.py`.

### Phase 3 — Market-research agent + dynamic fan-out  (~2 days)
- **New** `agent/market_research_agent.py`: given the profile's target wards,
  spawn one sub-agent **per ward concurrently** (`asyncio.gather` over a
  *dynamic* list — handles "you don't know upfront how many qualify"). Each
  ward sub-agent reads signals via `services/providers_jp/` +
  `market_state.build_snapshot` (deterministic gate), then makes ONE optional
  narrative Claude call for judgment. Returns a `WardVerdict`. Failing wards
  drop out.
- **Hybrid note:** the deterministic signal read decides pass/fail; the Claude
  call only annotates *why*. Flag-controlled so it can be disabled for cost.

### Phase 4 — Discovery agent + wire the fan-out  (~1 day)
- **New** `agent/discovery_agent.py`: thin wrapper over
  `services/property_recommender.py`, scoped to surviving wards from Phase 3.
  Returns N candidate `Property` rows. (Deterministic — no Claude.)
- **Wire fan-out:** orchestrator runs `analyst_council.review_listing` on each
  candidate concurrently via `asyncio.gather` guarded by an `asyncio.Semaphore`
  (CLAUDE.md rule #4 — never fire unbounded Claude calls).
- **Fan-in:** all scorecards → `services/synthesis.py` (Phase 1) → ranked
  recommendation → `AnalysisRun.result` → status `done`.

### Phase 5 — Frontend + cost guardrails  (~1 day)
- React "Run Analysis" page: start a run, show live agent-tree progress, pause
  on `needs_input`, render final ranking.
- **Cost guardrail (critical):** the dangerous number is `4 × N`. Add
  `MAX_FANOUT_PROPERTIES` (default ~15) and display the estimated Claude-call
  count *before* the run executes.

### Cost math to keep in mind
```
Intake          : 1 call
Market research : 1 per qualifying ward (~3–8)
Discovery       : 0 (deterministic)
Analysis        : 4 × N properties
Synthesis       : 0 (deterministic)

Typical run: 5 wards + 15 properties = 1 + 5 + 60 + 0 = ~66 calls (mostly Haiku)
```
That 66 is the number to cap and surface in the UI.

---

## 3. Runtime — Ubuntu as external operator

**Decision: Option A now.** The expensive work (66 parallel Claude calls +
Monte Carlo sims) is a background job, not request/response — that is what we
push off the Mac.

### Option A — whole backend on Ubuntu, Mac is just a screen  (do this first)
```
Mac (browser) ──HTTPS/Tailscale──► Ubuntu host: uvicorn main:app + Postgres + Redis
```
Buys immediately:
- All Claude fan-out, Monte Carlo, DCF run on Ubuntu's CPU, not the Mac.
- **Sidesteps the rollup/WASM problem** (the native rollup binary fails
  code-signing on this Mac; on Ubuntu it works natively and builds faster).

Setup on Ubuntu:
```bash
git clone <repo> && cd real-estate-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill ANTHROPIC_API_KEY, DATABASE_URL, SUPABASE_*
alembic upgrade head
python scripts/seed_properties.py
uvicorn main:app --host 0.0.0.0 --port 8000
```
Point the frontend `VITE_API_BASE` at the Ubuntu host over a Tailscale/SSH
tunnel (do **not** expose it publicly without auth enabled).

### Option B — worker/queue split  (later, when one run isn't enough)
```
Mac/browser ─► API (accepts requests) ─insert AnalysisRun(queued)─► Postgres
                                                                        │
                              Ubuntu worker pool (1..N procs) ◄─────────┘
                              claim run → orchestrator.run_analysis() → write result
```
- `POST /api/runs` just inserts a row and returns instantly — Mac does ~zero work.
- **New** `worker.py`: loop claiming `queued` runs, executing the orchestrator,
  streaming progress into the row.
- Scale by running `worker.py` N times. The `Semaphore` inside each run caps
  Claude concurrency per run.
- **Prerequisite:** the Postgres-backed run store from Phase 0 (an in-memory
  dict cannot be shared across API + worker processes).

### Recommendation
- **Now:** Option A. One Ubuntu box, everything on it, tunnel in. Zero new code,
  immediate relief, fixes the WASM build.
- **After Phase 4:** add `worker.py` (~1 file) for Option B so long runs don't
  tie up an HTTP request and workers scale horizontally.

---

## 4. New / changed files at a glance

| File | Phase | Kind |
|---|---|---|
| `db/models.py` (`AnalysisRun`) | 0 | model |
| `alembic/versions/<rev>_add_analysis_runs.py` | 0 | migration |
| `api/schemas.py` (`RunRequest`, `RunStatusResponse`, `Recommendation`) | 0–1 | schema |
| `services/synthesis.py` | 1 | service (pure) |
| `agent/orchestrator.py` | 2 | agent (asyncio glue) |
| `agent/intake_agent.py` | 2 | agent (1 Claude call) |
| `api/orchestrator.py` + mount in `main.py` | 2 | router |
| `agent/market_research_agent.py` | 3 | agent (per-ward fan-out) |
| `agent/discovery_agent.py` | 4 | agent (deterministic) |
| orchestrator fan-out wiring + `Semaphore` | 4 | glue |
| frontend "Run Analysis" page + cost cap | 5 | UI |
| `worker.py` | post-4 | Option B entrypoint |

Tests alongside each (`tests/test_synthesis.py`, `tests/test_orchestrator.py`,
`tests/test_intake_agent.py`, …), in-memory SQLite + mocked Anthropic, per the
existing testing conventions.

---

## 5. Open risks / watch-items
- **In-memory run store** in `strategy_runner.py` is the pattern to NOT copy.
  Phase 0 must be Postgres-backed or Option B is impossible.
- **Unbounded fan-out** — always gate `asyncio.gather` over listings with a
  `Semaphore`; surface the call-count estimate before executing.
- **Auth-by-payload debt** (`user_email`/`user_name` threaded through schemas,
  `services/user_resolve.py`) still stands from the prior review — fold the
  `AnalysisRun.user_id` into `Depends(current_user)` rather than a payload field.
