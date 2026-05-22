# Investor Portfolio — Implementation Plan (live)

> This document captures the plan that is **currently being executed** in the
> active Claude Code session on `real-estate-agent`. It is a living record of
> what was scoped, what shipped, and what is still in flight.
>
> Plan origin: memory observation **#S28** — *"Investor-focused /portfolio page
> plan for real-estate-agentic platform — spec review, conflict check, and full
> implementation plan produced (May 14 at 12:53 AM)"*.
> Active session: `claude --resume 6c066174-211c-4528-9063-3931dbb3ef29`.

---

## 1. Goal

Stand up a first‑class **investor surface** on the real‑estate‑agentic platform
so individual retail investors and owner‑operators can:

1. Track a portfolio of holdings (address, financials, status).
2. Underwrite a deal from a **Zillow URL** with first‑class HUD FMR + FRED rates.
3. Run a **Monte Carlo stress test** over the five core sliders (vacancy, rent
  growth, expense growth, loan rate, exit cap) and see the p10/p50/p90 band
   plus a tornado decomposition.
4. Get a **policy‑driven recommendation** per holding (`HOLD`, `RAISE_RENT`,
  `REFI`, `SELL`, `IMPROVE`) sourced from the existing pure‑Python
   `DecisionRuntime`.
5. Inspect the **tenant pool** that would plausibly rent / occupy a unit and
  ask "where is this neighborhood heading?" via prebuilt trajectory presets.
6. Toggle between **institutional** and **individual** modes from the top nav.

The MVP is scoped to **Zillow‑only** listing import with an **accurate Monte
Carlo simulation** (observation #1283).

## 2. Constraints inherited from the codebase

These were honored throughout the plan — none of them have been broken:

- **Pure‑Python domain runtime.** `domain/` is I/O‑free and must stay that way.
`DecisionRuntime` is reused in P4 by adding a thin I/O wrapper in `api/`.
- **Event sourcing.** All state changes write to `domain_events`. Portfolio
mutations follow this contract.
- **Test isolation.** Tests use in‑memory SQLite with JSONB→JSON patching and
fakeredis. No phase introduced a hard dependency on Postgres or Redis at
test time.
- **Tool ACL + guardrails.** Untouched. Investor endpoints are read‑only or
scoped to the calling user's own portfolio.
- **Naming conventions.** All new tables use the existing
`Alembic + UUID + idempotent guard` pattern (observation #1293).

## 3. Phase plan


| Phase  | Title                                                            | Status | Owner artifact(s)                                                                                           |
| ------ | ---------------------------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------- |
| **P1** | DB models + Portfolio CRUD API                                   | ✅ done | `db/models.py`, `api/portfolio.py`, migration `a72c98e5f441`                                                |
| **P2** | Underwriting engine + Zillow listing import + HUD/FRED providers | ✅ done | `intelligence/underwriting.py`, `services/listing_import.py`, `services/signal_providers/{hud_fmr,fred}.py` |
| **P3** | Monte Carlo stress test + batch sim API + FEMA/ACS providers     | ✅ done | `intelligence/stress_test.py`, `services/signal_providers/{fema_nfhl,census_acs}.py`                        |
| **P4** | `DecisionRuntime` exposure as `/api/decisions/holding/{id}`      | ✅ done | `api/decisions.py`                                                                                          |
| **P5** | Tenant pool + neighborhood trajectory backends                   | ✅ done | `services/tenant_pool.py`                                                                                   |
| **P6** | Frontend `PortfolioPage` + mode toggle + components              | ✅ done | `frontend/src/pages/PortfolioPage.tsx` + `frontend/src/components/portfolio/`*                              |
| **P7** | Documentation updates                                            | ✅ done | `doc/`*, `CLAUDE.md`                                                                                        |


Cumulative test status as of the live session: **560 passed, 0 failures** on
the backend suite after P5 (`pytest tests/ -q` → `560 passed, 1664 warnings in 5.60s`).

---

## 4. Phase-by-phase detail

### P1 — DB models + Portfolio CRUD API ✅

**Schema additions (`db/models.py`):**

- `PortfolioMode` enum (`institutional` | `individual`) — drives the top‑nav
surface (observation #1302).
- `UserProfile.preferred_mode` column — persisted user default
(observation #1303).
- `InvestorPortfolio`, `PortfolioHolding`, `HoldingFinancials` ORM models
(observation #1304).

**Migration:** `alembic/versions/a72c98e5f441_add_investor_portfolio_tables.py`
(observation #1305), idempotent‑guard pattern.

**API surface (`api/portfolio.py`, mounted at `/api/portfolio`):**

```
GET    /api/portfolio?user_id={id}
POST   /api/portfolio
GET    /api/portfolio/{portfolio_id}
DELETE /api/portfolio/{portfolio_id}
GET    /api/portfolio/{portfolio_id}/holdings
POST   /api/portfolio/{portfolio_id}/holdings
DELETE /api/portfolio/{portfolio_id}/holdings/{holding_id}
GET    /api/portfolio/{portfolio_id}/aggregate
```

The `aggregate` endpoint computes holding count, total value, equity, cost
basis, blended cap rate, weighted DSCR, asset‑class mix, and concentration in
pure Python from the holdings + financials rows (no separate analytics
service introduced).

**Tests:**

- `tests/test_portfolio_models.py` — ORM unit tests (observation #1299).
- `tests/test_api_portfolio.py` — CRUD integration (observation #1300).
- **Phase result:** 13/13 GREEN; full‑suite regression 511 passed
(observations #1309, #1310).

### P2 — Underwriting engine + Zillow listing import + HUD/FRED providers ✅

**Pure‑Python engine (`intelligence/underwriting.py`):**

- `UnderwritingInputs` / `UnderwritingResult` dataclasses.
- Computes monthly PITI, annual debt service, EGI, NOI, cap rate,
cash‑on‑cash, DSCR, breakeven occupancy, initial equity, and 5/10‑yr IRR.
- IRR solver replaced from Newton‑Raphson → **bisection** mid‑phase to fix an
`OverflowError` on stressed negative‑cash‑flow deals (observations #1327,

#1328). The bisection solver is what P3's Monte Carlo depends on.

**Basic tax modeling:** `intelligence/tax_basic.py` (observation #1319).

**Listing import:** `services/listing_import.py` parses Zillow URLs and
extracts `zpid`, `address_hint`, `state`, `zip_code` (observation #1320).
Errors surface as `ListingParseError`.

**Signal providers (extending the existing registry pattern):**

- `services/signal_providers/hud_fmr.py` — HUD Fair Market Rent
(observation #1321).
- `services/signal_providers/fred.py` — FRED mortgage rate
(observation #1322).
- Registered in `services/signal_providers/registry.py` and exported via
`services/signal_providers/__init__.py` (observations #1323, #1324).

**API surface (`api/underwrite.py`):**

```
POST /api/underwrite           → UnderwriteResponse
POST /api/listing/parse        → { source, zpid, url, address_hint, state, zip_code }
```

Pydantic schemas live in `api/schemas.py` (observation #1325).

**Tests:** 26/26 GREEN; full‑suite regression 537 passed
(observations #1329, #1330).

### P3 — Monte Carlo stress test + FEMA/ACS providers ✅

**Engine (`intelligence/stress_test.py`):**

- Five sliders sampled uniformly per iteration:
`vacancy_rate`, `rent_growth`, `expense_growth`, `loan_rate`, `exit_cap_rate`.
- Deterministic via `seed`.
- Outputs `cap_rate_`*, `cash_on_cash_`*, `dscr_*`, `irr_5yr_*` at p10/p50/p90,
`probability_negative_cash_flow`, `probability_dscr_under_1`, and a
**tornado decomposition** identifying which slider moves IRR the most.

**Robustness note.** IRR can fail to converge in deeply stressed scenarios.
The test assertion accepts ≥ 50% of iterations resolving — the runtime
returns the resolved subset rather than crashing the whole batch.

**Signal providers:**

- `services/signal_providers/fema_nfhl.py` — flood hazard zones.
- `services/signal_providers/census_acs.py` — ACS demographic context.
- Both registered in the existing registry; covered by
`tests/test_fema_acs_providers.py`.

**API surface (extends `api/underwrite.py`):**

```
POST /api/underwrite/stress-test  → StressTestResponse
```

Schemas added to `api/schemas.py`:

- `SliderRangeSchema`
- `StressTestConfigSchema` (with sensible defaults: vacancy 3–15%, rent growth
0–4%, expense growth 2–4%, loan rate 5–8%, exit cap 6–8.5%)
- `StressTestRequest`
- `StressTestResponse`

**Tests:** `tests/test_stress_test.py`, `tests/test_api_stress_test.py`,
`tests/test_fema_acs_providers.py` — all GREEN.

### P4 — `DecisionRuntime` exposure as `/api/decisions/holding/{id}` ✅

`api/decisions.py` is the read‑only investor decision surface. It wires the
pure‑Python `DecisionRuntime` (`ListHoldPolicy` + `LeasePolicy` + `ChurnPolicy`)
over a holding's market context + financials, then maps policy outputs onto
five investor‑facing actions:


| Action       | Trigger source                                    |
| ------------ | ------------------------------------------------- |
| `HOLD`       | Default / no other policy fires                   |
| `RAISE_RENT` | `LeasePolicy` signals headroom vs comp rents      |
| `REFI`       | Financial heuristic on rate spread + DSCR cushion |
| `SELL`       | `ListHoldPolicy` says exit beats hold             |
| `IMPROVE`    | `ChurnPolicy` flags turnover/condition risk       |


The runtime stays pure; the API module owns the I/O (loading the holding,
building the market snapshot) and the policy→investor‑action mapping.

**API surface:**

```
GET /api/decisions/holding/{holding_id}  → HoldingDecisionResponse
```

Pydantic schemas added to `api/schemas.py`:

- `DecisionCandidate { action, score, rationale, source }`
- `HoldingDecisionResponse { holding_id, recommendation, score, rationale, market_context_available, candidates[] }`

Router registered in `main.py` at `/api/decisions`.

**Tests:** `tests/test_api_decisions.py` — 5/5 GREEN.

### P5 — Tenant pool + neighborhood trajectory backends ✅

`services/tenant_pool.py` provides:

- `INCOME_BANDS` — canonical bands (`low`, `moderate`, `middle`, `upper`).
- `TenantPoolFilter` — zip / income band / housing type / voucher filter.
- `query_tenant_pool(...)` — filtered query over `HouseholdProfile` rows.
- `summarize_pool(...)` — aggregate count, median income, voucher share,
eviction‑risk percentiles.
- `list_trajectory_presets()` / `get_trajectory_preset(name)` — a small
registry of **prebuilt topic + round bundles** that drive the existing
social‑simulation loop (`services/social_simulator.py`) for a "where is
this neighborhood heading" view without forcing the caller to hand‑pick
topics. Topics are validated against `domain.reactions.social_dynamics.ALLOWED_REACTION_TOPICS`.

**Tests:** `tests/test_tenant_pool.py` — 9/9 GREEN; full‑suite regression
560 passed.

### P6 — Frontend `PortfolioPage` + mode toggle + components ✅

**Status: done.** All four tabs, the CSV importer, the mode toggle, and the
test infra are shipped and green: `npx vitest run` → **14 passed (2 files)**,
`npx playwright test` → **1 passed**, `npm run build` → clean.

**Types & API client** (`frontend/src/utils/{types,api}.ts`):

- Added `PortfolioMode`, `InvestorPortfolio`, `PortfolioHolding`,
`HoldingFinancials`, `PortfolioHoldingCreate`, `PortfolioAggregate`,
`UnderwriteRequest`, `UnderwriteResponse`, `SliderRange`,
`StressTestConfig`, `StressTestResponse`, `DecisionCandidate`,
`HoldingDecisionResponse`.
- Added typed `api.portfolio.`*, `api.underwrite.`*, `api.listing.*`,
`api.decisions.*` client groups against the new backend endpoints.

**CSV import** (`frontend/src/utils/csvImport.ts`):

- Dependency‑free CSV parser.
- Auto‑detects **Stessa** and **REI Hub** export layouts (the two most
common rental bookkeeping tools); falls back to a generic `address`‑column
parser.
- Normalizes rows into `PortfolioHoldingCreate`.
- Unit‑tested in `frontend/src/utils/csvImport.test.ts`.

**Components (`frontend/src/components/portfolio/`):**

- `CsvImportPanel.tsx` — drag‑and‑drop CSV import with editable preview rows.
- `HoldingsTab.tsx` — list / add / delete holdings with aggregate row.
- `UnderwriteTab.tsx` — single‑deal underwriting form bound to
`/api/underwrite`.
- `StressTestTab.tsx` — slider ranges + run button bound to
`/api/underwrite/stress-test`; renders the p10/p50/p90 table.
- `DecisionsTab.tsx` — per‑holding recommendation pulled from
`/api/decisions/holding/{id}` with action blurbs (`HOLD`, `RAISE_RENT`,
`REFI`, `SELL`, `IMPROVE`).

**Page + nav:**

- `frontend/src/pages/PortfolioPage.tsx` — owns user/portfolio selection and
tab routing.
- `frontend/src/hooks/usePortfolioMode.ts` — localStorage + cross‑component
broadcast for the top‑nav mode toggle.
- `frontend/src/App.tsx` — registers `/portfolio` route behind `RequireAuth`,
adds the **Portfolio** nav link, and renders `<PortfolioModeToggle />` in
the header.

**Testing infra:**

- `vitest` + `jsdom` + `@testing-library/react` + `@testing-library/jest-dom`
installed; `src/test/setup.ts` wires `jest-dom` matchers.
- `playwright` installed; `playwright.config.ts` boots Vite and runs
`e2e/portfolio.spec.ts` (asserts the Portfolio nav link is present and
the mode toggle flips and persists across reload).
- `package.json` adds `test`, `test:watch`, `test:e2e` scripts.

**rollup optional‑deps fix:** the `@rollup/rollup-darwin-arm64` native binary
is rejected by macOS code‑signing on this machine ("different Team IDs"). The
durable fix — applied in `frontend/package.json` — is an `overrides` entry
pinning `rollup` to the dependency‑free WASM build:

```json
"overrides": { "rollup": "npm:@rollup/wasm-node@^4" }
```

This unblocks `vitest`, `vite dev`, and `vite build` without the native
binary. No source changes were needed.

**Final styling:** `frontend/src/styles/index.css` gained a
`/* Investor Portfolio (Phase P6) */` block covering the page shell, tabs,
aggregate/result grids, CSV import table, and the decision panel.

### P7 — Documentation updates ✅

Shipped:

- This file — status table + P4–P7 detail brought current.
- `CLAUDE.md`:
  - Four new API routers (`portfolio`, `underwrite` + `/listing/parse`,
  `decisions`) added to the directory + router map.
  - New ORM models listed on the `db/models.py` line.
  - pytest count bumped 498 → 560; the four new signal providers
  (`hud_fmr`, `fred`, `fema_nfhl`, `census_acs`) added to the providers
  table; `DecisionRuntime` marked **wired** via `/api/decisions`.
- `doc/PLATFORM_WORKFLOWS.md` — investor portfolio workflow appended.
- `doc/investor-workflows.md` — new concise, user‑facing walkthrough of the
four‑tab investor surface.

---

## 5. End‑to‑end investor flow

```
User
 │  (toggle mode → "individual" in top nav)
 ▼
PortfolioPage
 ├── Holdings tab
 │     ├── POST /api/portfolio                    (create portfolio)
 │     ├── POST /api/portfolio/{id}/holdings      (add holding, manual or CSV)
 │     ├── DELETE /api/portfolio/{id}/holdings/{hid}
 │     └── GET   /api/portfolio/{id}/aggregate    (blended cap rate, DSCR, mix)
 │
 ├── Underwrite tab
 │     ├── POST /api/listing/parse                (Zillow URL → zpid + address)
 │     └── POST /api/underwrite                   (cash-on-cash, cap, DSCR, IRR)
 │           ↑ pulls HUD FMR rent floor + FRED mortgage rate from registry
 │
 ├── Stress test tab
 │     └── POST /api/underwrite/stress-test       (Monte Carlo, p10/p50/p90, tornado)
 │
 └── Decisions tab
       └── GET /api/decisions/holding/{hid}       (DecisionRuntime → HOLD / RAISE_RENT
                                                   / REFI / SELL / IMPROVE)
```

Tenant pool + trajectory presets (P5) are wired through the existing
`services/social_simulator.py` loop and surface as a future "Neighborhood"
tab once P6 styling is locked.

## 6. Files touched (cumulative, P1–P6)

**Backend — new:**

- `intelligence/underwriting.py`
- `intelligence/tax_basic.py`
- `intelligence/stress_test.py`
- `services/listing_import.py`
- `services/tenant_pool.py`
- `services/signal_providers/hud_fmr.py`
- `services/signal_providers/fred.py`
- `services/signal_providers/fema_nfhl.py`
- `services/signal_providers/census_acs.py`
- `api/portfolio.py`
- `api/underwrite.py`
- `api/decisions.py`
- `alembic/versions/a72c98e5f441_add_investor_portfolio_tables.py`
- `tests/test_underwriting.py`
- `tests/test_tax_basic.py`
- `tests/test_stress_test.py`
- `tests/test_listing_import.py`
- `tests/test_hud_fred_providers.py`
- `tests/test_fema_acs_providers.py`
- `tests/test_api_underwrite.py`
- `tests/test_api_stress_test.py`
- `tests/test_api_decisions.py`
- `tests/test_api_portfolio.py`
- `tests/test_portfolio_models.py`
- `tests/test_tenant_pool.py`

**Backend — modified:**

- `db/models.py` (PortfolioMode, InvestorPortfolio, PortfolioHolding,
HoldingFinancials, UserProfile.preferred_mode)
- `api/schemas.py` (portfolio, underwrite, stress test, decision schemas)
- `services/signal_providers/registry.py`
- `services/signal_providers/__init__.py`
- `main.py` (registers `portfolio_router`, `underwrite_router`,
`listing_router`, `decisions_router`)

**Frontend — new:**

- `frontend/src/pages/PortfolioPage.tsx`
- `frontend/src/components/portfolio/HoldingsTab.tsx`
- `frontend/src/components/portfolio/UnderwriteTab.tsx`
- `frontend/src/components/portfolio/StressTestTab.tsx`
- `frontend/src/components/portfolio/DecisionsTab.tsx`
- `frontend/src/components/portfolio/CsvImportPanel.tsx`
- `frontend/src/components/portfolio/CsvImportPanel.test.tsx`
- `frontend/src/hooks/usePortfolioMode.ts`
- `frontend/src/utils/csvImport.ts`
- `frontend/src/utils/csvImport.test.ts`
- `frontend/src/test/setup.ts`
- `frontend/vitest.config.ts`
- `frontend/playwright.config.ts`
- `frontend/e2e/portfolio.spec.ts`

**Frontend — modified:**

- `frontend/src/utils/types.ts`
- `frontend/src/utils/api.ts`
- `frontend/src/App.tsx`
- `frontend/src/styles/index.css` (Phase P6 style block)
- `frontend/package.json` (vitest + playwright scripts + deps + `rollup` WASM override)

## 7. Verification commands

```bash
# Backend (from real-estate-agent/)
python -m pytest tests/ -q
#   expected: 560 passed (after P5; P6 is frontend-only)

python -m pytest tests/test_api_portfolio.py tests/test_portfolio_models.py -v
python -m pytest tests/test_api_underwrite.py tests/test_api_stress_test.py -v
python -m pytest tests/test_api_decisions.py tests/test_tenant_pool.py -v

# Frontend (from real-estate-agent/frontend/)
npm install            # recover node_modules if needed
npm run test           # vitest run
npm run test:e2e       # playwright (boots vite dev server)
```

## 8. Open risks & follow‑ups

- **IRR convergence under stress.** P3 currently accepts a partial IRR sample
set (≥ 50% of iterations). If a future feature depends on a full sample,
we'll need to revisit either the bisection bracket or the underlying cash
flow generator.
- **HUD / FRED / FEMA / ACS providers** are wired against the registry but
rate‑limit / API‑key behavior is provider‑specific; production keys live in
`.env` and are *not* required at test time.
- **Authentication on `/api/portfolio`** mirrors the existing `users` router —
endpoints are not yet guarded by Supabase JWT (observation #1296). This is
intentional pre‑MVP but must be revisited before any public release.
- **P6 npm bug — resolved.** The `@rollup/rollup-darwin-arm64` native binary
is rejected by macOS code‑signing on this machine. Fixed durably via a
`rollup` → `@rollup/wasm-node` `overrides` entry in `frontend/package.json`
(see P6 detail). If the native binary is ever needed back, remove the
override and reinstall on a machine without the signing conflict.

## 9. Memory references

Observations cited in this plan (for context retrieval via
`get_observations([IDs])`):

- #S28 — plan origin
- #1280, #1282 — pre‑plan gap analysis
- #1283 — MVP scope decision (Zillow + accurate MC)
- #1284 — P1 task
- #1285 — P2 task
- #1286 — P3 task
- #1287 — P4–P7 tasks
- #1288–#1298 — pre‑P1 codebase confirmation
- #1299–#1310 — P1 execution
- #1311–#1330 — P2 execution + IRR fix

