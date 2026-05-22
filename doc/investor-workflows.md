# Investor Workflows

User-facing walkthrough of the individual-investor surface. For the build
record and phase history see
[`investor-portfolio-implementation-plan.md`](./investor-portfolio-implementation-plan.md);
for how it fits the wider platform see
[`PLATFORM_WORKFLOWS.md`](./PLATFORM_WORKFLOWS.md).

## Who this is for

Individual retail investors and owner-operators tracking a small portfolio of
rentals — not institutional desks. The **mode toggle** in the top nav switches
the platform's framing between *institutional* and *individual*; it is a manual,
localStorage-backed switch and persists across reloads within a browser.

## Getting in

`/portfolio` is behind authentication. Sign in, then pick (or create) an
investor and a portfolio in the selectors at the top of the page. The page is
a six-tab workspace — **Overview** is the default landing tab.

## Tab 1 — Overview *(default)*

One read-only consolidated report. On portfolio select, the backend fans out
analysis across **every holding** — underwrites each from stored financials,
runs the decision policy per holding, and rolls up aggregates. You see:

- A headline aggregate strip — holding count, total value, equity, monthly
  cash flow, blended cap rate, weighted DSCR.
- A **"what needs attention"** callout listing holdings flagged for non-HOLD
  actions (SELL / REFI / IMPROVE / RAISE_RENT), sorted by score.
- A per-holding analysis table with cap rate, DSCR, CoC, monthly cash flow,
  and recommendation per holding.
- A market-coverage note: how many holdings have market signals available.

Backed by `GET /api/portfolio/{id}/summary` →
`services/portfolio_summary.build_portfolio_summary`, which composes
`intelligence/underwriting.py` and `services/holding_decision.py` per holding.

## Tab 2 — Holdings

Track the properties you own.

- **Add a holding** manually: address, zip, asset class, monthly rent.
- **Prefill from a Zillow listing**: paste a listing URL → the address and zip
  are parsed and dropped into the form. You still review and **override** every
  field before saving — the listing only seeds the form.
- **Import a CSV**: upload an export from **Stessa** or **REI Hub**. The format
  is auto-detected (an unknown layout falls back to a generic `address`-column
  parser). Parsed rows appear in an **editable table** — override anything,
  then commit the import.
- The **aggregate strip** shows holding count, total value, total equity,
  monthly cash flow, blended cap rate, and weighted DSCR across the portfolio.

## Tab 3 — Underwrite

A single-deal underwriting calculator. Enter purchase price, financing, rent,
and operating assumptions; get back cap rate, cash-on-cash return, DSCR,
annual NOI, monthly PITI, breakeven occupancy, and 5/10-year IRR.

## Tab 4 — Stress Test

A Monte Carlo stress test over five sliders — vacancy rate, rent growth,
expense growth, loan rate, and exit cap rate. Set the low/high range for each
and the iteration count; the result is the p10 / p50 / p90 band for cap rate
and DSCR plus the probability of negative cash flow and of DSCR falling
under 1.0.

## Tab 5 — Decisions

Pick a holding and get a recommendation. The backend runs the pure-Python
`DecisionRuntime` (list/hold + lease + churn policies) over the holding's
market context and financials, adds a refinance heuristic, and maps everything
onto five investor actions:

| Action | Meaning |
|---|---|
| `HOLD` | Stay the course — no action recommended. |
| `RAISE_RENT` | Rent has room to move toward market. |
| `REFI` | The note rate is high enough to make refinancing worthwhile. |
| `SELL` | Market conditions favor listing this holding. |
| `IMPROVE` | Invest in the property to protect tenant retention. |

The response includes the top recommendation plus every scored candidate and
its rationale. When a holding has no market signals, the recommendation is
driven by financials only and the UI says so explicitly.

## Tab 6 — Strategy

Describe your current investing strategy or opinion in free text — *"long-term
buy and hold, low risk, 4% rent growth, protect tenants"* — and the backend
runs analysis **and** simulation end to end. Three steps:

1. **Describe.** Type your strategy in plain English.
2. **Review the extracted profile.** The backend converts the text into a
   structured `StrategyProfile` (assumptions / policy / thesis). Every field is
   editable — same seed-then-confirm pattern as the Zillow listing prefill.
3. **Run.** A background job runs the Overview-tab analysis parametrized by
   your profile and projects each holding forward by the profile's hold
   period. You get a **Unified Report**:

   - whether the strategy *survives* the projection (with a confidence score);
   - agreements (recommendations that stay stable) and divergences
     (recommendations that flip);
   - a per-holding table showing today's vs. projected action, projected
     value, projected cap rate, and a flip explanation when the action moves.

Backed by `POST /api/strategy/extract`, `POST /api/strategy/run`,
`GET /api/strategy/{id}/status`, `GET /api/strategy/{id}/result`. State lives
in an in-process store guarded by `asyncio.Lock` —
`services.strategy_runner.{start,execute,get}_strategy_run` — matching the
batch-simulator pattern.

The simulation stage is **pure-Python and deterministic**: it projects
per-holding NOI by `(1+rent_growth-expense_growth)^hold_years`, projects value
by `(1+0.03+outlook_tilt)^hold_years`, then re-runs a small rule engine to
pick the projected action (SELL on cash-flow collapse, REFI on loan-rate
outlook, IMPROVE/HOLD under tenant protection, RAISE_RENT under explicit
bias). No LLM call inside the run — extraction is the only LLM-eligible seam.

## Tenant pool & trajectory presets

`services/tenant_pool.py` backs a "who would rent this, and where is the
neighborhood heading" view: income-band-aware filtering over synthetic
households plus prebuilt social-simulation presets (`neighborhood_trajectory`,
`displacement_pressure`). These are wired through the existing
`services/social_simulator.py` loop and will surface as a future
**Neighborhood** tab.

## Testing

- Backend: `python -m pytest tests/ -q` (560 tests, no external services).
- Frontend unit: `cd frontend && npm run test` (Vitest).
- Frontend E2E: `cd frontend && npm run test:e2e` (Playwright; boots Vite).
