# Tier 1 Implementation Plan: Satei-to-Close Tools for Tokyo Brokerages

**Target:** 3 features that transform the platform from analysis tool to "satei-to-close" SaaS for 不動産仲介 brokerages.

**Target decisions the platform helps brokers make:**
1. Satei/valuation (査定) — highest frequency, every listing pitch
2. Asking-price — high stakes, mispricing = #1 cause of slow sales
3. Accept/counter + reservation-price — negotiation coaching

## Overview & Dependencies

Feature A: Satei Comp Grid ← foundation, other features consume it
Feature B: Price-vs-Probability Curve ← builds on satei + simulation engine
Feature C: Negotiation Strategy Coach ← builds on both, mostly repositioning existing code

Execution order: A → B → C

---

## Feature A: Satei Comp Grid (査定コンプグリッド) — 10 days

### What It Does

Automated comparable-based valuation for listing pitches. Broker inputs a property → system pulls REINFOLIB transaction data + rent comps → applies hedonic adjustments → produces a defensible satei price with an editable comp adjustment grid (spreadsheet-style, broker can override adjustments).

### Database Changes

**New table: `satei_sessions`**

```python
# db/models.py
class SateiSession(Base):
    __tablename__ = "satei_sessions"

    id              = Column(String, primary_key=True, default=uuid_gen)
    user_id         = Column(String, ForeignKey("user_profiles.id"), nullable=False)
    property_id     = Column(String, ForeignKey("properties.id"), nullable=True)

    # Input snapshot
    address         = Column(String, nullable=False)
    menseki_m2      = Column(Float, nullable=False)
    built_year      = Column(Integer, nullable=True)
    construction_type = Column(String, nullable=True)
    walk_minutes    = Column(Integer, nullable=True)
    zip_code        = Column(String, nullable=True, index=True)

    # Result
    satei_price_yen = Column(BigInteger, nullable=True)
    confidence_low  = Column(BigInteger, nullable=True)
    confidence_high = Column(BigInteger, nullable=True)
    comps_used      = Column(JSONB, nullable=True)         # list of adjusted comp dicts
    adjustment_grid = Column(JSONB, nullable=True)         # broker-editable overrides

    created_at      = Column(DateTime, default=func.now())
    updated_at      = Column(DateTime, default=func.now(), onupdate=func.now())
```

**New table: `sale_comps`**

```python
class SaleComp(Base):
    __tablename__ = "sale_comps"

    id                = Column(String, primary_key=True, default=uuid_gen)
    zip_code          = Column(String, nullable=False, index=True)
    ward_code         = Column(String, nullable=True, index=True)

    # Transaction data from REINFOLIB
    source            = Column(String, nullable=False)          # "reinfolib", "manual"
    source_record_id  = Column(String, nullable=True)
    address_hint      = Column(String, nullable=True)
    menseki_m2        = Column(Float, nullable=True)
    built_year        = Column(Integer, nullable=True)
    construction_type = Column(String, nullable=True)
    walk_minutes      = Column(Integer, nullable=True)
    floor_level       = Column(Integer, nullable=True)

    # Sale-specific fields (distinct from rent_comps)
    transaction_date  = Column(Date, nullable=True)
    actual_sale_price = Column(BigInteger, nullable=False)
    asking_price      = Column(BigInteger, nullable=True)
    days_on_market    = Column(Integer, nullable=True)

    fetched_at        = Column(DateTime, default=func.now())
    expires_at        = Column(DateTime, nullable=True)         # stale after 90 days
```

**Migration:** `alembic revision --autogenerate -m "add_satei_sessions_and_sale_comps"`

### Hedonic Adjustment Engine

**New service: `services/satei_engine.py`**

```python
@dataclass(frozen=True)
class AdjustedComp:
    comp_id: str
    raw_price: int
    adjusted_price: int
    adjustments: dict[str, float]    # factor_name -> pct modifier

@dataclass(frozen=True)
class SateiResult:
    satei_price: int
    confidence_band_low: int
    confidence_band_high: int
    comps_used: list[AdjustedComp]
    adjustment_grid: dict            # serializable grid for frontend

async def compute_satei(
    db: AsyncSession,
    address: str,
    menseki_m2: float,
    built_year: int | None,
    construction_type: str | None,
    walk_minutes: int | None,
    zip_code: str,
    *,
    overrides: dict | None = None,   # broker adjustment overrides
) -> SateiResult:
```

**Adjustment factors per comp:**

| Factor | Logic | Example |
|--------|-------|---------|
| `age_diff` | +1.5% per year newer, -1.5% per year older | Subject 2020, comp 2018 → +3% |
| `floor_area_diff` | +0.5% per m² larger, -0.5% per m² smaller (capped ±15%) | Subject 60m², comp 55m² → +2.5% |
| `walk_time_diff` | -1% per additional minute walk, +1% per fewer | Subject 5min, comp 8min → +3% |
| `construction_type` | RC vs SRC vs S vs W relative adjustment table | W→RC → +8% |
| `floor_level` | +1% per floor above ground (1F baseline) | 1F→5F → +4% |

**Computation:**
- Filter comps: same zip, menseki ±30%, walk ±5min (same as rent validator)
- Apply adjustment factors to each comp's actual_sale_price
- Weighted average of adjusted prices = satei_price (weight by recency + similarity)
- Confidence band = ±1 standard deviation of adjusted prices

### Reused Code

| Existing Module | What We Reuse |
|----------------|---------------|
| `services/rent_validator.py` | Clone filtering logic (zip, menseki ±30%, walk ±5min) |
| `services/signal_providers/reinfolib_transaction.py` | Extend to return individual transaction records, not just municipality medians |
| `api/rent_comps.py` | Endpoint pattern for comp-related routes |
| `intelligence/underwriting.py` | Supporting metrics (cap rate, NOI) for satei context |
| `services/broker_report.py` | Report output pattern for satei document generation |

### API Endpoints

```python
# api/satei.py
router = APIRouter(prefix="/api/satei", tags=["satei"])

@router.post("/compute")
async def compute_satei(body: SateiComputeRequest, db=Depends(get_db)):
    """Takes property details + optional filter params, returns SateiResult with comp grid."""

@router.get("/{id}")
async def get_satei_session(id: str, db=Depends(get_db)):
    """Retrieve saved satei session."""

@router.patch("/{id}/adjustments")
async def update_adjustments(id: str, body: AdjustmentUpdate, db=Depends(get_db)):
    """Broker updates individual adjustments, server recomputes satei price."""

@router.get("/{id}/document")
async def get_satei_document(id: str, format: str = "json", db=Depends(get_db)):
    """Generate formatted satei document (JSON or PDF)."""
```

### Frontend

**New page: `SateiPage.tsx`** (route: `/satei`)

- Property input form (address, menseki, built_year, construction_type, walk_minutes)
- Editable comp adjustment grid — spreadsheet-style table where each row is a comp, columns are adjustment factors, broker can override any cell, totals auto-recompute
- Result panel: satei price with confidence band, bar chart of comp distribution
- "Generate Satei Document" button for PDF export

### Effort Estimate

| Task | Days |
|------|------|
| DB models + migration | 0.5 |
| Extend REINFOLIB provider for individual records | 1.5 |
| Satei engine service | 2 |
| API endpoints | 1 |
| Frontend SateiPage + editable grid | 3 |
| Tests | 2 |
| **Total** | **10 days** |

---

## Feature B: Price-vs-Probability Curve (価格帯別成約確率カーブ) — 12 days

### What It Does

Given a property's satei value, produce a curve showing: "if you list at X yen, the probability of closing within 30/60/90/180 days is Y%." This is the broker's primary tool for the asking-price conversation with the seller.

### Architecture

- Takes property + satei value + asking price range (satei -10% to satei +20%, in 2% steps)
- For each price point, runs N Monte Carlo simulations (default 100) varying buyer demand, market conditions, seasonal factors
- Uses historical REINFOLIB transaction data to calibrate time-on-market distributions
- Each simulation determines: does the property sell? If so, at what price and after how many days?
- Aggregates into probability buckets: P(close within 30d), P(close within 60d), P(close within 90d), P(close within 180d)

### Reused Code

| Existing Module | What We Reuse |
|----------------|---------------|
| `intelligence/stress_test.py` | Monte Carlo engine with SliderRange parameter draws, directly reusable as outer loop |
| `domain/simulation/loop.py` | `run_simulation()` with convergence detection, core engine |
| `domain/simulation/models.py` | `SimConfig`, `SimResult`, `PropertyState` |
| `api/simulation_unified.py` | Clone endpoint pattern |
| `services/signal_providers/reinfolib_transaction.py` | Historical data for time-on-market calibration |

### New Code

**`services/price_probability.py`**

```python
@dataclass(frozen=True)
class PriceProbabilityPoint:
    asking_price: int
    p30: float                        # probability of close within 30 days
    p60: float
    p90: float
    p180: float
    expected_settlement_price: int
    expected_days_on_market: float

@dataclass(frozen=True)
class PriceProbabilityCurve:
    property_id: str
    satei_price: int
    points: list[PriceProbabilityPoint]
    generated_at: datetime
    simulation_count: int

async def compute_price_probability_curve(
    db: AsyncSession,
    property_id: str,
    satei_price: int,
    *,
    price_range_pct: tuple[int, int] = (-10, 20),
    step_pct: int = 2,
    simulations: int = 100,
) -> PriceProbabilityCurve:
```

**`api/price_probability.py`**

```python
router = APIRouter(prefix="/api/price-probability", tags=["price-probability"])

@router.post("/compute")
async def compute_curve(body: PriceProbabilityRequest, db=Depends(get_db)):
    """Compute price-vs-probability curve for a property."""

@router.get("/{id}")
async def get_curve(id: str, db=Depends(get_db)):
    """Retrieve a previously computed curve."""
```

### Frontend

Tab or linked view within `SateiPage.tsx`:

- Interactive Recharts line chart: X-axis = asking price, Y-axis = probability, 4 lines (30d, 60d, 90d, 180d)
- Vertical slider/marker for the recommended asking price
- Table below showing expected settlement price and days-on-market per price point
- "Sweet spot" highlight: price where p90 > 80% (high confidence of closing within 90 days)

### Effort Estimate

| Task | Days |
|------|------|
| Price probability service | 3 |
| Monte Carlo calibration with REINFOLIB data | 2 |
| API endpoints | 1 |
| Frontend chart + table | 3 |
| Integration with SateiPage | 1 |
| Tests | 2 |
| **Total** | **12 days** |

---

## Feature C: Negotiation Strategy Coach (交渉戦略コーチ) — 7 days

### What It Does

Repositions the existing multi-agent negotiation simulator as a broker coaching tool. Instead of "simulate a negotiation," it becomes "rehearse scenarios before your next meeting." The broker inputs the property, their client's reservation price, and the counterparty's likely profile, then explores what-if scenarios.

**Important positioning:** This is a coaching/strategy-exploration tool, NOT an oracle. Academic research shows LLM negotiation agents exhibit anchoring bias and midpoint miscalculation — the value is in scenario exploration, not prediction.

### Reused Code (extensive — mostly repositioning)

| Existing Module | What We Reuse |
|----------------|---------------|
| `frontend/src/pages/NegotiationPage.tsx` | Social simulation panel, offer ledger, event replay |
| `domain/simulation/loop.py` | Simulation loop |
| `domain/decisions/` | `DecisionRuntime` with negotiation policy |
| `domain/reactions/` | `ReactionVector`, `ReactionEngine`, narrative clustering |
| `domain/reports/` | `NegotiationBriefing`, `ReplayNarrative` |
| `api/market_simulation.py` | Persona archetype pattern for counterparty modeling |

### New Code

**`services/negotiation_coach.py`** — Thin orchestration wrapper:

```python
@dataclass(frozen=True)
class CoachingSession:
    property_id: str
    client_profile: str              # "seller" or "buyer"
    reservation_price: int
    batna: str | None                # best alternative to negotiated agreement
    counterparty_profiles: list[dict]

@dataclass(frozen=True)
class CoachingResult:
    recommended_opening: int
    concession_ladder: list[int]
    walk_away_points: list[dict]
    zopa_analysis: dict
    scenario_summaries: list[dict]

async def run_coaching_session(
    db: AsyncSession,
    session: CoachingSession,
) -> CoachingResult:
```

**Prompt updates in `agent/analyst_personas.py`** — add "Negotiation Strategist" persona focused on:
- Counterparty motivation analysis
- Concession pattern prediction
- ZOPA estimation
- Walk-away point identification

**Frontend relabeling in `NegotiationPage.tsx`:**
- "Your client" instead of "investor"
- "Counterparty" instead of "opponent"
- "Rehearse scenario" instead of "run simulation"
- Add coaching-specific input panel: client reservation price, BATNA, counterparty profile selector

### Effort Estimate

| Task | Days |
|------|------|
| Negotiation coach service | 2 |
| Persona/prompt updates | 1 |
| Frontend relabeling + coaching panel | 2 |
| Tests | 2 |
| **Total** | **7 days** |

---

## Total Effort Summary

| # | Feature | Days | Dependencies |
|---|---------|------|-------------|
| A | Satei Comp Grid | 10 | None (foundation) |
| B | Price-vs-Probability Curve | 12 | Satei result as input, simulation engine (exists) |
| C | Negotiation Strategy Coach | 7 | Both above for context, but mostly code exists |
| | **Total** | **29 days** | |

With parallelization (2 engineers):
- Week 1-2: Feature A (both engineers)
- Week 3-4: Feature B (engineer A) + Feature C (engineer B)
- Week 5: Integration testing + polish
- Timeline: ~5 weeks with 2 engineers

Solo developer timeline: ~6 weeks

## New Database Tables Summary

| Table | Feature | Purpose |
|-------|---------|---------|
| `satei_sessions` | A | Persisted satei runs with results |
| `sale_comps` | A | Cached individual REINFOLIB transaction records |

## New API Routers Summary

| Router | Prefix | Feature |
|--------|--------|---------|
| `satei` | `/api/satei` | A |
| `price_probability` | `/api/price-probability` | B |

## New Frontend Pages Summary

| Page | Route | Feature |
|------|-------|---------|
| `SateiPage.tsx` | `/satei` | A + B (tabs) |
| `NegotiationPage.tsx` (modified) | `/negotiate` | C (relabeled) |

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| REINFOLIB API rate limits at scale | Feature A delayed | Cache aggressively in sale_comps; batch fetch off-hours; 1 req/sec rate limit |
| Insufficient historical data for time-on-market calibration | Feature B accuracy | Use synthetic calibration from aggregate stats; label confidence bands clearly |
| Brokers expect REINS integration not REINFOLIB | Feature A perceived incomplete | REINFOLIB is the public API over REINS data — document equivalence; plan direct REINS as Tier 2 |
| NegotiationPage relabeling breaks existing tests | Feature C regression | Update selectors and assertions during relabeling |
| LLM negotiation agents have known biases (anchoring, midpoint miscalculation) | Feature C credibility | Position explicitly as coaching tool, not oracle; show confidence ranges |

## Tier 2 Features (Deferred from Previous Plan)

These investor-focused features may return in a future tier, adapted for the brokerage context:
- Comparative Deal Analyzer → broker property comparison tool
- AI Listing Scout → market monitoring for brokerages
- Natural Language Thesis → natural language property brief for client presentations
- Broker Report Generator → already absorbed into Feature A (satei document output)

---

*Plan generated June 14, 2026. Pivot from investor co-pilot to brokerage satei-to-close SaaS.*
