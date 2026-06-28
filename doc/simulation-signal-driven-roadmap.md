# Signal-Driven Simulation — Gap Analysis & Roadmap

**Status:** Research / proposal (2026-06). Grounded in the current code:
`services/strategy_runner.py`, `services/portfolio_summary.py`,
`services/market_state.py`, `domain/market/models.py`, `intelligence/`.

Goal: make the Portfolio **Simulation** tab project holdings forward using the
**live market signals the platform already collects**, instead of being sealed
to the user's `StrategyProfile` assumptions.

---

## 1. Data / APIs already available (but unused by the simulation)

Everything normalizes into a `MarketContextSnapshot` (`domain/market/models.py`)
via `services/market_state.build_snapshot`.

| Signal | Source provider | Snapshot field | Scope |
|---|---|---|---|
| `median_sale_price` | Census ACS (`B25077_001E`) | `median_sale_price` | per zip |
| `median_rent` | HUD FMR, Census ACS (`B25064_001E`) | `median_rent` | per zip |
| `mortgage_rate_30yr` | FRED `MORTGAGE30US` | *(not yet mapped to snapshot)* | national |
| `inventory_pressure` | schema-ready (no live provider yet) | `inventory_pressure` | per zip |
| `safety_score` | Chicago crime (`ijzp-q8t2`) | `safety_score` | per zip |
| `hazard` (flood zone) | FEMA NFHL | `hazard_flags` | **per property** |
| `transit_score` / `school_score` | mock fixture | those fields | per zip |

Property value today = `HoldingFinancials.current_value_estimate` (a **static
stored number**). `median_sale_price` exists but never revalues anything; there
is no AVM.

## 2. The core gap

`project_simulation` / `_project_holding` (`services/strategy_runner.py`) are
**hermetically sealed to `StrategyProfile`**:

- appreciation = hardcoded `3% + outlook_tilt` (`±0.02 / ±0.015`)
- rent growth = `profile.assumptions.rent_growth` (user number)
- NOI growth = `(1 + rent_growth - expense_growth) ** H`
- refi decision keys off `profile.assumptions.loan_rate_outlook` (a guess)
- exit cap = static `profile.assumptions.exit_cap_rate`

`MarketContextSnapshot` is **never passed in** — even though
`build_portfolio_summary` already loads it (it uses it for *holding decisions*,
not for the projection math). `_per_holding_metrics` is purely financial
(`HoldingFinancials` columns only).

**Ground-truth formulas to reuse** (`intelligence/underwriting.py`):
`cap = NOI/value`, `DSCR = NOI/debt_service`, `CoC = annual_CF/equity`,
IRR via bisection, JP depreciation via 簡便法 (`intelligence/depreciation_jp.py`).

## 3. Architecture path (the unlock)

One refactor enables everything — thread the snapshot into the **pure** projection:

```python
# strategy_runner.execute_strategy_run(): db + analysis already in hand
snapshots = await build_snapshots(db, [h.property_id for h in holdings if h.property_id])
live_rate = await latest_signal(db, "mortgage_rate_30yr", "jurisdiction", "US")  # FRED

simulation = project_simulation(
    analysis, profile, snapshots=snapshots, live_mortgage_rate=live_rate
)
# project_simulation -> _project_holding(row, profile, snapshot=snapshots.get(row["holding_id"]))
```

The projection stays **pure** (snapshot passed as an argument, never fetched) —
honoring the domain-purity rule. ~30 lines of plumbing; the formulas below then
plug into `_project_holding`.

## 4. Best formula (signal-driven projection)

Blend the user's thesis with live signals via a confidence weight `α`
(market-trust vs. user-trust; start `α ≈ 0.5`). For each holding over horizon `H`:

**a) Appreciation — anchor to comps, not a flat 3%:**
```
market_growth     = (snapshot.median_sale_price / holding.current_value) ** (1/H) - 1
g_value           = α·market_growth + (1-α)·(0.03 + outlook_tilt)
projected_value   = current_value · (1 + clamp(g_value, -0.05, 0.10)) ** H
```

**b) Rent growth — pull toward neighborhood median (mean reversion):**
```
rent_gap_growth   = (snapshot.median_rent / holding.monthly_rent) ** (1/H) - 1
g_rent            = clamp(α·rent_gap_growth + (1-α)·profile.rent_growth, -0.02, 0.06)
projected_NOI     = today_NOI · (1 + g_rent - expense_growth) ** H
```

**c) Exit cap — flex with inventory pressure:**
```
exit_cap = profile.exit_cap_rate · (1 + 0.15·(inventory_pressure - 0.5))
# tight market (low pressure) -> lower cap -> higher exit value
```

**d) Refi — replace the guess with the live FRED rate:**
```
if live_mortgage_rate and (holding.interest_rate - live_mortgage_rate) > 0.0075:
    action          = REFI
    refi_confidence = clamp((holding.interest_rate - live_mortgage_rate) / 0.02, 0, 1)
```

**e) Risk haircuts — make hazard/safety cost money:**
```
if hazard_flags.in_special_flood_hazard_area:
    projected_value *= 0.95;  insurance *= 1.4
vacancy_eff = base_vacancy · (1 + 0.10·(1 - safety_score/10))   # unsafe -> more turnover
```

**f) Survival verdict (feeds the existing `UnifiedReport`):**
keep `reconcile_unified_report`, but weight `confidence = 1 - flips/total` by
**signal coverage** (`market_coverage.with_signals / total`) — "survives on live
comps" should outscore "survives on assumptions."

## 5. Prioritized roadmap

1. **Quick win (~20 lines):** map FRED `mortgage_rate_30yr` into the pipeline +
   rule (d). Highest signal/effort — turns a user guess into a real arbitrage check.
2. **Plumbing refactor:** thread `snapshots` into `project_simulation` (§3).
3. **(b) rent reversion**, then **(a) appreciation anchoring** — biggest accuracy
   gains; data already present (HUD / Census).
4. **(e) risk haircuts** (FEMA / crime) + **(c) inventory exit-cap** — refinements.
5. **Later:** a small AVM that writes a `median_sale_price`-calibrated value
   signal, so Analysis and Simulation share one market-anchored value.

## 6. Constraints (must hold)

- `domain/` stays pure/deterministic/lenient — signals enter as function args.
- New state changes → `domain_events` with correlation id (already wired for runs).
- Market-signal reads via `services/market_state` / `signal_writer`; providers
  inject `httpx.AsyncClient` for tests.
- Extend existing `SimulationReport` / `UnifiedReport` schemas additively.
