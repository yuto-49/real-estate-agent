# Strategy Runtime — Implementation Plan (live)

> Status: S1–S8 + S10 shipped. S9 deferred as an optional follow-up.
> The pipeline is live behind `/api/portfolio/{id}/summary`,
> `/api/strategy/extract`, `/api/strategy/run`, `/api/strategy/{id}/status`,
> and `/api/strategy/{id}/result`, surfaced in the frontend as the new
> **Overview** (default) and **Strategy** tabs on `/portfolio`.
>
> This document captures the plan that has been executed. It folds together
> two ideas raised in conversation:
>
> 1. A **portfolio-level auto-summary** — one consolidated, read-only report on
>    the Portfolio page that fans out analysis across every holding.
> 2. A **`StrategyRun` pipeline** — the user puts in their current investing
>    strategy or opinion once, and analysis + simulation run automatically end
>    to end.
>
> The key realization that lets these be one plan: the portfolio summary **is**
> the analysis half of the strategy pipeline. Build the summary first; the
> strategy pipeline wraps strategy input around it and adds the simulation half.
>
> Builds on the now-complete investor surface — see
> [`investor-portfolio-implementation-plan.md`](./investor-portfolio-implementation-plan.md)
> and [`investor-workflows.md`](./investor-workflows.md).

---

## 1. Goal

Collapse the current four manual single-shot tabs (Holdings / Underwrite /
Stress Test / Decisions) into a flow where the user supplies intent once and
the platform produces a consolidated, forward-looking report automatically:

1. **Auto-summary.** On portfolio select, fan out analysis across *all*
   holdings server-side and present one read-only `PortfolioSummaryReport` —
   aggregates, per-holding analysis, and a "what needs attention" callout.
2. **Strategy input.** The user describes their current investing strategy or
   opinion in free text. The platform structures it into a reviewable
   `StrategyProfile` (LLM seeds the fields, user overrides every one — the same
   pattern as the existing Zillow listing prefill).
3. **Automatic analysis + simulation.** A `StrategyRunner` chains the analysis
   stage (the summary above) into a simulation stage that projects the holdings
   forward under the user's thesis, then reconciles both into a
   `UnifiedReport`: *does this strategy survive its own projection?*

---

## 2. The core architectural idea

The platform already has the spine — the layered domain runtime:

```
market → actor → reaction → decision → outcome → report
```

**Analysis** produces the left side (today's state): market snapshot, actor /
holding state, financials. **Simulation** projects the right side forward.

So the unification is not new machinery — it is an *orchestrator* that chains
existing components, with the analysis output handed in directly as the
simulation's initial conditions. The one architectural commitment:

> **`AnalysisReport` (= `PortfolioSummaryReport`) is the typed seed for the
> simulation stage.** Market snapshot, actor / holding state, and the derived
> reaction vector pass straight through — no re-derivation.

### The user's "strategy or opinion" decomposes into three structured inputs

Free text is not what the engine consumes. A strategy structures cleanly into
three things existing components already accept:

| User says... | Becomes... | Feeds... |
|---|---|---|
| "rents rise 4%/yr, 8% vacancy, 10-yr hold" | **Assumptions** | underwrite inputs + Monte Carlo slider ranges |
| "buy-and-hold, low risk, protect tenants" | **Policy config** | which `DecisionRuntime` policies + thresholds |
| "this zip is gentrifying / displacement risk" | **Thesis** | social-sim trajectory preset + `ReactionVector` |

### Pipeline shape

```
StrategyInput (free text + portfolio_id)
  → StrategyProfile          # structured: assumptions + policy config + thesis
  → AnalysisStage            # underwrite + decision (+ optional stress) per holding
      → PortfolioSummaryReport   # ← the auto-summary; also the simulation seed
  → SimulationStage          # SocialSimulator + intelligence tick, seeded from the report
      → SimulationReport
  → UnifiedReport            # reconciles analysis vs projection
```

---

## 3. Constraints inherited from the codebase

- **Pure-Python domain runtime.** `domain/` stays I/O-free. `DecisionRuntime`
  and the social simulator are *reused*, never modified — orchestration lives
  in `services/` and `api/`.
- **Reuse, don't re-derive.** The decision logic currently inside
  `api/decisions.py` must be extracted into a service function so both the
  endpoint and the summary aggregator call one implementation.
- **Heavy work runs in the background.** Monte Carlo over N holdings and the
  intelligence tick pipeline are too heavy for a sync request — they reuse the
  existing `api/batch_simulation.py` start / status / result job pattern.
- **Event sourcing.** A `StrategyRun` is a state change → it writes to
  `domain_events`.
- **Test isolation.** In-memory SQLite + fakeredis, no hard Postgres/Redis
  dependency at test time.
- **Seed-then-confirm UX.** Free-text → `StrategyProfile` is the riskiest link;
  the LLM only seeds the form, the user reviews and overrides every field
  before a run starts.

---

## 4. Phase plan

| Phase  | Title | Status | Owner artifact(s) |
| ------ | ----- | ------ | ----------------- |
| **S1** | Extract decision logic into a service | ✅ done | `services/holding_decision.py` (from `api/decisions.py`) |
| **S2** | `PortfolioSummaryReport` schema + aggregator | ✅ done | `api/schemas.py`, `services/portfolio_summary.py` |
| **S3** | `GET /api/portfolio/{id}/summary` endpoint | ✅ done | `api/portfolio.py` |
| **S4** | Overview tab — auto-summary frontend (new default tab) | ✅ done | `frontend/src/components/portfolio/OverviewTab.tsx` |
| **S5** | `StrategyProfile` schema + free-text extractor | ✅ done | `api/schemas.py`, `services/strategy_profile.py` |
| **S6** | `StrategyRunner` orchestrator + background job | ✅ done | `services/strategy_runner.py`, `api/strategy.py` |
| **S7** | `UnifiedReport` builder | ✅ done | `services/unified_report.py` |
| **S8** | Strategy frontend — input → review profile → run → report | ✅ done | `frontend/src/components/portfolio/StrategyTab.tsx` |
| **S9** | Stress rollup as a background job (optional) | ⏸ deferred | `services/portfolio_summary.py` (`include_stress`) |
| **S10** | Documentation updates | ✅ done | `doc/`*, `CLAUDE.md` |

Cumulative backend test status after S8: **585 passed, 0 failures**
(`pytest tests/ -q` — +25 new tests this session: 5 `test_portfolio_summary`,
2 `test_api_portfolio_summary`, 7 `test_strategy_profile`, 11
`test_strategy_runner`). Frontend tests: 4 files, 20 vitest tests passing.

S1–S4 deliver the auto-summary and stand alone. S5–S8 add the strategy
pipeline on top. S9–S10 are follow-ups.

---

## 5. Phase-by-phase detail

### S1 — Extract decision logic into a service

`api/decisions.py` currently inlines the snapshot build, reaction derivation,
`DecisionRuntime` run, policy→investor-action mapping, refi heuristic, and
dedupe. Move that into `services/holding_decision.py` as a function returning
the existing `HoldingDecisionResponse` shape. `api/decisions.py` becomes a thin
caller. No behavior change — existing `tests/test_api_decisions.py` must stay
green.

### S2 — `PortfolioSummaryReport` schema + aggregator

**Schema (`api/schemas.py`):**

```
PortfolioSummaryReport {
  portfolio_id, generated_at, holding_count,
  aggregates { total_value, total_equity, monthly_cash_flow,
               blended_cap_rate, weighted_dscr },
  per_holding [ { holding_id, address, cap_rate, dscr, coc,
                  recommendation, score, rationale } ],
  attention  [ holdings flagged SELL / REFI / IMPROVE ],
  market_coverage { with_signals, total }
}
```

**`services/portfolio_summary.py`:** loads the portfolio's holdings +
financials, calls the underwriting engine and `services/holding_decision.py`
per holding, rolls up aggregates, collects flagged holdings. Pure composition
over existing services — no new domain logic.

### S3 — `GET /api/portfolio/{id}/summary` endpoint

Synchronous. Underwrite + decisions across a retail-sized portfolio is light.
Scoped to the caller's own portfolio. `?include_stress=true` is reserved for
S9 and not wired yet.

### S4 — Overview tab (new default tab)

New first tab on `PortfolioPage`, made the default landing tab. Auto-fetches
the summary on portfolio select. Renders, top to bottom: headline aggregate
strip → "what needs attention" callout → per-holding analysis table →
market-coverage note. Loading + empty states. The Holdings tab keeps its own
aggregate strip — Overview is a superset, not a replacement.

### S5 — `StrategyProfile` schema + free-text extractor

**Schema:** `StrategyProfile { assumptions {...}, policy_config {...},
thesis {...} }` per the decomposition table in §2.

**`services/strategy_profile.py`:** an LLM call that parses
`StrategyInput.text` into a `StrategyProfile`, with every field defaulted so a
sparse description still produces a valid, fully-overridable profile.

### S6 — `StrategyRunner` orchestrator + background job

`services/strategy_runner.py` chains `AnalysisStage` (the S2 aggregator,
parametrized by the profile's assumptions + policy config) → `SimulationStage`
(the social simulator + intelligence tick, seeded from the
`PortfolioSummaryReport` and steered by the profile's thesis). Runs as a
background job — `api/strategy.py` exposes `POST /api/strategy/run`,
`GET /api/strategy/{id}/status`, `GET /api/strategy/{id}/result`, reusing the
`batch_simulation` job pattern.

### S7 — `UnifiedReport` builder

`services/unified_report.py` reconciles the `PortfolioSummaryReport` against
the `SimulationReport`: does the today-state recommendation still hold once the
holdings are projected forward under the user's thesis? Surfaces agreements,
divergences, and the holdings whose recommendation flips under projection.

### S8 — Strategy frontend

A Strategy tab (or top-level page): free-text box → review the extracted
`StrategyProfile` (every field editable) → run → poll status → render the
`UnifiedReport`.

### S9 — Stress rollup as a background job (optional)

Wires `?include_stress=true` on the summary endpoint to a background Monte
Carlo rollup across holdings, so the headline summary stays fast and the stress
band fills in a beat later.

### S10 — Documentation updates

Update `investor-workflows.md` (new Overview + Strategy tabs), `CLAUDE.md`
(routers, services, test count), `PLATFORM_WORKFLOWS.md`, and mark this plan
live once S1 starts.

---

## 6. Decisions to settle before S1

- **Sync vs background split.** Recommended: sync for underwrite + decisions,
  background for the Monte Carlo stress rollup (S9) and the full strategy run
  (S6). Tradeoff: the headline loads fast; the stress band and simulation show
  up a beat later.
- **Free-text parsing vs. structured form.** Recommended: LLM seeds the
  `StrategyProfile`, user confirms — consistent with the existing Zillow
  prefill UX. Tradeoff: one extra confirm step vs. silent misinterpretation of
  the user's strategy.
- **Recompute vs cache the summary.** Recommended: recompute every visit (the
  data is small) but stamp `generated_at` for freshness.
- **Where the Neighborhood / tenant-pool view fits.** The P5 tenant pool +
  trajectory presets are the natural backing for the thesis → simulation leg —
  this pipeline is a good reason to finally surface them (the deferred
  Neighborhood tab).
- **First-cut scope.** Single portfolio, Zillow-only signals, the two existing
  trajectory presets — matching the investor-MVP scoping.
