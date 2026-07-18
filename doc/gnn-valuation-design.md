# GNN-Based Valuation & Price-Movement Design

> **Status:** Research + design proposal (2026-07-14). No code yet.
> **Scope:** How a Graph Neural Network fits this project as a *comparable-aware
> valuation and price-movement engine*, fed by the MLIT **reinfolib** (不動産情報
> ライブラリ) API, without breaking the pure-`domain/` boundary.

---

## 0. The question, answered directly

You asked whether the GNN:

- **(A)** takes the features of each neighbouring house and looks at the *connections*, or
- **(B)** looks at how *prices move* and works out how *your* target house would move,
  respecting the neighbourhood's features.

**Both are real GNN formulations, and they are not rivals — they are two different
axes of the same model.** The right design for this app uses both:

| Axis | Question it answers | GNN mechanism |
|------|--------------------|---------------|
| **A — Relational / structural** | *"What is this house worth, given its comparables?"* | **Message passing**: a node's representation = its own features **+** an aggregation of messages from connected neighbour nodes. This is literally "look at neighbour features across the connections." |
| **B — Temporal / diffusion** | *"If the area moves, how does *this* house move?"* | **Spatio-temporal GNN**: the same message passing, but over a *sequence* of time slices, so a price shock or trend **diffuses** across edges to the target node. |

So the honest answer is: a node (your house) never predicts in isolation. Message
passing pulls in neighbour features **through the edges** (A). Stacking that over
time lets a movement in the neighbourhood **propagate** to your house at a rate the
edges encode (B). One model, two heads:

- **Valuation head** → price *level* (₩/㎡ or total ¥) — cross-sectional, axis A.
- **Momentum head** → expected price *movement* over horizon *h* — spatio-temporal, axis B.

Everything below concretises this into a structure that fits the existing
FastAPI + pure-`domain/` + `MarketSignal` architecture.

---

## 1. Why a graph at all (the domain justification)

Real-estate prices are the textbook case of **spatial autocorrelation** — Tobler's
first law: *"near things are more related than distant things."* A house's value is
overwhelmingly explained by *comparable* nearby transactions ("comps"). Classic
hedonic regression treats each property as i.i.d. and throws that structure away.
A GNN keeps it:

- **Comps become neighbours** — the model learns *which* comps matter and *how much*
  (GAT attention weights), instead of a hand-tuned "within 500 m, same ward" filter.
- **Sparse features borrow strength** — a property with a missing feature inherits
  signal from its neighbourhood (matches this repo's *lenient projections* ethos).
- **Shocks propagate** — a new station, a hazard re-zoning, or a comp selling 15 %
  over ask diffuses to connected nodes with a learned decay.

This is the same "neighbourhood signal" idea the codebase already encodes in
`services/market_state.py` (neighbourhood signals looked up under `neighborhood_id`
and `zip_code`) — the GNN is the *learned, continuous* version of that lookup.

---

## 2. Data foundation — reinfolib (MLIT 不動産情報ライブラリ)

The current provider (`services/providers_jp/reinfolib.py`) is a **mock** reading
CSV fixtures and exposes:

- `get_transactions(city_code, from_year, to_year)` → rows with
  `取引価格(総額)`, `面積(㎡)`, `最寄駅:距離(分)`, `建築年`, `市区町村コード`
- `get_price_index(city_code)` → `median_price`, `count`, `yoy_change` (placeholder)

The **real** reinfolib API (free, API-key gated — `config.reinfolib_api_key`
already exists) provides far more, and maps cleanly onto graph elements:

| reinfolib endpoint (family) | Content | Graph role |
|---|---|---|
| Transaction prices (取引価格情報 / 成約価格情報) | Per-deal price, area, structure, built year, station+walk mins, zoning, city code, quarter | **Transaction nodes** (features + the **label** we train on) |
| Municipality list (市区町村一覧) | city_code ↔ name | Node keys / area rollups |
| Land-price public notice & survey (地価公示・地価調査) | Official ¥/㎡ per point, multi-year | **Area anchor nodes** + a clean price-trend signal (fills today's `yoy_change` gap) |
| Appraisal reports (鑑定評価) | Professional valuations | High-trust node features / supervision anchors |
| GIS point & polygon layers (GeoJSON tiles): stations, schools, zoning (用途地域), hazard, population mesh, urban-planning | POIs, boundaries | **Edge builders & context features** (shared-station edges, same-zoning edges, hazard/pop context) |

**Key point for the GNN:** reinfolib is unusually well-suited because it gives *both*
halves at once — the **transaction records** (node features + supervised price labels)
**and** the **spatial/GIS layers** (the scaffolding to draw meaningful edges). Most
price-model datasets give only the first.

**Ingestion path (reuse, don't reinvent):**
1. Promote `ReinfolibProvider` to a real HTTP impl behind the existing Protocol
   (mirror the `MockSignalProvider` → real-provider pattern; `tenacity` retry +
   injected `httpx.AsyncClient`, per critical-pattern #4).
2. Land raw transactions into the DB (either enrich `Property` rows or a new
   `transactions` table — see §6). GIS layers cached as fixtures/tiles.
3. Derived area trends (land-price YoY, median ¥/㎡) written as **`MarketSignal`s**
   via `services/signal_writer.upsert_signal` (idempotent per calendar day) — never
   `db.add(MarketSignal(...))` directly (critical-pattern #8).

---

## 3. Graph schema

### 3.1 Nodes (heterogeneous)

| Node type | Source | Example features |
|---|---|---|
| **Property** (the ones a user underwrites) | `properties` table | `menseki_m2`, `built_year`→age, `structure`/`construction_type`, `youto_chiiki` (zoning), `kenpei_ritsu`/`youseki_ritsu`, `walk_minutes_to_station`, `ward_code`, `hazard_flags`, lat/lon |
| **Transaction** | reinfolib transactions | price/㎡ (**label**), area, age at sale, structure, walk mins, quarter |
| **Area anchor** (chōchō / station / mesh) | reinfolib land-price + GIS | official ¥/㎡, YoY, population, zoning mix |

A homogeneous first cut (Property + Transaction only, projected to a shared feature
space) is a valid MVP; the heterogeneous version is the target.

### 3.2 Edges (this is where the "connections" live)

| Edge type | Rule | Encodes |
|---|---|---|
| **Spatial k-NN** | Haversine distance; connect *k* nearest, weight `exp(−d/τ)` | Tobler proximity |
| **Same-station** | Shares a `nearest_stations` entry | Commute-market substitutability |
| **Same-zoning** | Same `youto_chiiki` | Regulatory comparability |
| **Same-building / same-block** | Shared `ward_code` + address prefix | Strata / micro-market |
| **Temporal** (axis B only) | Same node across consecutive quarters | Movement diffusion carrier |

Edge weights are features too — the model learns e.g. that same-station matters more
than raw distance near a hub.

### 3.3 Features → tensors

A pure, deterministic **feature projection** belongs in `domain/` (no I/O, frozen
dataclasses, lenient on missing → sensible default). The torch tensor assembly and
the model live in `services/` (ML deps are not allowed in `domain/`).

---

## 4. Model architecture

```
             ┌──────────────────────── shared GNN encoder ───────────────────────┐
 node feats ─┤  L× ( GraphSAGE / GAT message passing over spatial+relational edges ) ├─┐
             └────────────────────────────────────────────────────────────────────┘ │
                                                                                      │  node embedding h_v
                          ┌───────────────────────────────────────────────────────────┤
                          │                                                            │
             ┌────────────▼─────────────┐                        ┌────────────────────▼───────────────┐
 axis A →    │  Valuation head (MLP)     │           axis B →     │  Momentum head                       │
             │  → price level ¥/㎡        │                        │  temporal GNN (T-GCN / GRU over the  │
             │  + prediction interval     │                        │  sequence of quarter-slices)         │
             └───────────────────────────┘                        │  → Δprice over horizon h + interval  │
                                                                   └──────────────────────────────────────┘
```

- **Encoder:** GraphSAGE (scalable, inductive — critical for *new* listings the model
  never saw at train time) or **GAT** (attention gives free explainability: the
  attention weight on each neighbour edge = *"how much did this comp drive the number"*).
  Start GraphSAGE, add attention once it works.
- **Valuation head (axis A):** regress log-price-per-㎡. Cross-sectional.
- **Momentum head (axis B):** wrap the encoder in a temporal cell (T-GCN = GCN + GRU,
  or temporal message passing) over T quarterly slices → predict Δ over horizon *h*.
  This is exactly your hypothesis (B): a movement in the neighbourhood propagates to
  the target node through the edges, at a learned rate.
- **Uncertainty:** quantile heads or MC-dropout → prediction intervals. The existing
  stress-test / Monte-Carlo surface (`intelligence/stress_test.py`) already speaks
  "distribution of outcomes," so intervals slot in naturally.
- **Inductive by construction** so a freshly-imported listing gets a value by attaching
  it to the existing graph and running one forward pass — no retrain.

**Library:** PyTorch Geometric (PyG) or DGL. Kept out of the core dependency set;
installed under an optional extra (e.g. `pip install -e ".[gnn]"`) so the API and the
347-test suite stay torch-free.

---

## 5. How it respects this project's architecture (the hard constraint)

The **iron rule** (CLAUDE.md critical-pattern #6): `domain/` is pure, deterministic,
side-effect-free, **no torch, no I/O**. A trained GNN is a heavy stateful artifact —
it **cannot** live in `domain/`. Resolution:

```
 reinfolib API ─▶ services/providers_jp/reinfolib.py (real HTTP, tenacity, httpx inject)
                        │
                        ▼
 offline:  scripts/train_gnn.py ──▶ graph build + train ──▶ model artifact (versioned)
                        │                                         │
                        ▼                                         ▼
 nightly:  scripts/precompute_gnn_signals.py ──▶ services/gnn/inference.py (loads artifact)
                        │
                        ▼
        services/signal_writer.upsert_signal(...)   # gnn_valuation, gnn_price_momentum
                        │                              (idempotent per calendar day)
                        ▼
        db: market_signals ──▶ services/market_state.build_snapshot ──▶ MarketContextSnapshot
                        │                                                     │
                        ▼                                                     ▼
        domain/  (STILL PURE) — consumes the numbers as plain floats in the snapshot;
                 the decision runtime + outcome projections use them like any other signal
                        │
                        ▼
        api/decisions.py, api/portfolio summary, Simulation tab
```

**Why this is the correct seam:**
- The GNN's *output* enters the system as a **`MarketSignal`** — the exact mechanism
  the codebase already uses for every spatial-market number. `domain/` never learns
  the model exists; it just sees `gnn_valuation` next to `median_sale_price`.
- Training + inference are **services/scripts** (allowed I/O + heavy deps), audited to
  `domain_events` via `EventStore.append` with a correlation id (critical-pattern #1),
  exactly like `strategy_runner` audits runs.
- Provider Protocol + mock/real duality (critical-pattern #3) extends to a
  `GnnValuationProvider` Protocol with a **heuristic mock** (k-NN comp average, no
  torch) so tests and bare-DB dev never need a GPU or model file.

### 5.1 Proposed file manifest

| Path | Responsibility | Deps |
|---|---|---|
| `domain/graph/features.py` | Pure feature projection: Property/txn → frozen feature vector; deterministic, lenient | none |
| `domain/graph/schema.py` | Node/edge type enums, edge-rule definitions (pure) | none |
| `services/gnn/graph_builder.py` | Pull rows (DB + reinfolib), build edge index, assemble tensors | SQLAlchemy, numpy |
| `services/gnn/model.py` | PyG model def (encoder + 2 heads) | torch, PyG |
| `services/gnn/inference.py` | Load artifact, forward pass, → valuation + momentum | torch |
| `services/gnn/provider.py` | `GnnValuationProvider` Protocol + `MockGnn` (k-NN heuristic) + `TorchGnn` | Protocol |
| `services/providers_jp/reinfolib.py` | **Extend**: real HTTP impl behind existing Protocol | httpx, tenacity |
| `scripts/train_gnn.py` | Offline training, temporal split, artifact versioning | torch |
| `scripts/precompute_gnn_signals.py` | Nightly batch → `upsert_signal` | — |
| `api/valuation.py` | `GET /api/properties/{id}/gnn-valuation`, `.../price-movement` | FastAPI |
| `tests/test_gnn_graph_builder.py`, `test_gnn_provider_mock.py` | Torch-free tests via the mock | pytest |

New signal types (join the existing `median_sale_price`, `inventory_pressure`,
`hazard`, …): **`gnn_valuation`**, **`gnn_valuation_interval`**, **`gnn_price_momentum`**.

---

## 6. Training pipeline

1. **Label:** log(price/㎡) from reinfolib transactions.
2. **Split — no leakage (critical):** split **by time**, not random. Train on
   quarters ≤ *t*, validate/test on quarters > *t*. Real-estate models leak
   catastrophically under random splits (a comp from *next* quarter predicting *this*
   sale). The momentum head *requires* the temporal split anyway.
3. **Graph build:** k-NN + relational edges (§3.2), computed within the train window
   only for train nodes.
4. **Train:** minimise valuation loss (Huber on log-price) + momentum loss (quantile),
   early-stop on the future validation quarter.
5. **Artifact:** version the weights + the feature spec + graph config together
   (`models/gnn/<version>/`). Record a `gnn.model_trained` domain event with metrics.
6. **Eval report:** MAE / MAPE on ¥/㎡, directional accuracy on momentum, coverage of
   the prediction interval — written like the existing unified-report artifacts.

---

## 7. Serving & product integration

- **Nightly precompute** (`scripts/precompute_gnn_signals.py`): for every active
  `Property`, attach to the graph, forward pass, `upsert_signal` the valuation +
  momentum. Batch keeps request latency at zero — reads are just signal lookups.
- **On-demand** `api/valuation.py`: for a freshly imported listing, build a local
  ego-graph and run one inductive forward pass.
- **Analysis tab** (`portfolio_summary.build_portfolio_summary`): show GNN valuation
  vs asking price ("comp-implied value: ¥X, −8 % vs ask") and the top-attention comps
  as the *explanation*.
- **Simulation tab** (`strategy_runner.project_simulation`): the **momentum head** is
  a natural forward-projection input — "neighbourhood moves +3 %, this holding is
  modelled to move +2.1 % given its edges." Reconciles through the existing
  `unified_report`.
- **Decisions** (`services/holding_decision.py` → `api/decisions.py`): list/hold gets a
  learned "priced above/below comp value" signal instead of a hand-tuned threshold.

---

## 8. Guardrails, evaluation, explainability

- **Explainability is first-class, not an afterthought:** GAT attention weights answer
  *"which comparables drove this number and by how much."* Surface the top-k
  attention edges in the API response — this is what turns a black box into something
  an investor trusts.
- **Cold start / sparse areas:** fall back to the k-NN heuristic mock (or the existing
  `median_sale_price` signal) when a node has too few edges. Log the fallback (never
  silently), matching the lenient-projection convention.
- **Drift:** re-train on a schedule; monitor future-quarter MAE; alert on degradation.
- **Leakage:** enforced temporal split (§6.2) + never letting a node see its own
  transaction in its neighbour set.
- **Determinism boundary:** the model is *non-deterministic to train* but its *output*
  is a plain number in a `MarketSignal` — so the pure `domain/` layer stays fully
  deterministic and testable. The non-determinism is quarantined in `services/`.

---

## 9. Phased rollout

| Phase | Deliverable | Torch? |
|---|---|---|
| **0 — Heuristic graph** | `MockGnn`: k-NN comp average + distance-weighted momentum, wired end-to-end (signals → snapshot → tabs). Proves the *plumbing*. | No |
| **1 — Real reinfolib** | Real HTTP `ReinfolibProvider`; land transactions; land-price YoY fills the `yoy_change` gap. | No |
| **2 — Cross-sectional GNN** | GraphSAGE valuation head; nightly precompute; Analysis-tab valuation vs ask. | Yes |
| **3 — Spatio-temporal** | Momentum head (T-GCN); Simulation-tab projection input. | Yes |
| **4 — Attention + explainability** | Swap to GAT; surface top comps; prediction intervals into stress-test. | Yes |

Phase 0 delivers user-visible value with **zero ML dependencies** and validates the
whole integration seam before any GPU is involved — the recommended starting point.

---

## 10. One-line summary

A house is a **node**; its comparables are **neighbours across weighted edges**;
**message passing** values it from those neighbours' features (your hypothesis A); a
**temporal** wrapper lets neighbourhood price *movement* diffuse to it (your
hypothesis B). reinfolib uniquely supplies **both** the node labels (transactions) and
the edge scaffolding (GIS layers). The model lives in `services/`, its output enters
as a **`MarketSignal`**, and the pure `domain/` pipeline consumes it unchanged.
```
```
