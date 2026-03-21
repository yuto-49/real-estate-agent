# Testing the Full System with the Real Estate Valuation CSV Dataset

This guide explains how to use `/Users/maruyamayuto/Downloads/Real estate valuation data set.csv` (414 records from Taiwan real estate transactions) to exercise the complete negotiation and intelligence pipeline.

---

## Dataset Overview

| Column | Meaning | Example |
|--------|---------|---------|
| `No` | Row index | 1 |
| `X1 transaction date` | Decimal year of transaction | 2012.917 |
| `X2 house age` | Age in years | 32 |
| `X3 distance to the nearest MRT station` | Meters to closest metro | 84.87 |
| `X4 number of convenience stores` | Count within living circle | 10 |
| `X5 latitude` | Latitude (Taipei area ~24.9x) | 24.98298 |
| `X6 longitude` | Longitude (Taipei area ~121.5x) | 121.54024 |
| `Y house price of unit area` | Price per ping (坪) in 10k NTD | 37.9 |

**Key adaptation needed**: The CSV prices are in NTD per unit area. The system expects USD total price. The seed script below converts them to approximate USD totals.

---

## Step 1: Create the CSV Seed Script

Create `scripts/seed_from_csv.py`:

```python
"""Seed the database from the Real Estate Valuation CSV dataset."""

import asyncio
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import async_session, engine, Base
from db.models import Property, UserProfile

CSV_PATH = Path.home() / "Downloads" / "Real estate valuation data set.csv"

# Conversion constants
NTD_TO_USD = 0.032          # approximate NTD → USD
PING_TO_SQFT = 35.58        # 1 ping ≈ 35.58 sqft
DEFAULT_SQFT = 900           # fallback unit size in sqft
PRICE_MULTIPLIER = 10_000    # Y column is in units of 10k NTD


def estimate_usd_price(price_per_unit_area: float, sqft: int = DEFAULT_SQFT) -> float:
    """Convert NTD-per-ping to a total USD price."""
    pings = sqft / PING_TO_SQFT
    total_ntd = price_per_unit_area * PRICE_MULTIPLIER * pings
    return round(total_ntd * NTD_TO_USD, -3)  # round to nearest $1k


def infer_property_type(house_age: float) -> str:
    """Rough heuristic: newer buildings in Taipei are often condos."""
    if house_age < 10:
        return "condo"
    elif house_age < 25:
        return "condo"
    else:
        return "sfr"


def infer_bedrooms(price_per_unit: float) -> int:
    if price_per_unit > 50:
        return 3
    elif price_per_unit > 30:
        return 2
    return 1


async def seed():
    if not CSV_PATH.exists():
        print(f"CSV not found at {CSV_PATH}")
        print("Place 'Real estate valuation data set.csv' in ~/Downloads/")
        sys.exit(1)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # --- Users ---
        buyer = UserProfile(
            name="Test Buyer",
            email="buyer@test.com",
            role="buyer",
            budget_min=150_000,
            budget_max=500_000,
            life_stage="relocating",
            investment_goals={"primary": "residence", "secondary": "appreciation"},
            risk_tolerance="moderate",
            timeline_days=90,
            latitude=24.975,
            longitude=121.540,
            zip_code="10608",
            preferred_types=["sfr", "condo"],
        )
        seller = UserProfile(
            name="Test Seller",
            email="seller@test.com",
            role="seller",
            budget_min=0,
            budget_max=0,
            life_stage="investor",
            investment_goals={"primary": "liquidation"},
            risk_tolerance="moderate",
            timeline_days=60,
            latitude=24.975,
            longitude=121.540,
            zip_code="10608",
        )
        db.add(buyer)
        db.add(seller)
        await db.flush()  # get IDs

        # --- Properties from CSV ---
        count = 0
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                price_per_unit = float(row["Y house price of unit area"])
                house_age = float(row["X2 house age"])
                lat = float(row["X5 latitude"])
                lng = float(row["X6 longitude"])
                mrt_distance = float(row["X3 distance to the nearest MRT station"])
                stores = int(row["X4 number of convenience stores"])

                sqft = DEFAULT_SQFT
                usd_price = estimate_usd_price(price_per_unit, sqft)

                prop = Property(
                    seller_id=seller.id,
                    address=f"Taipei #{row['No'].strip()}, {mrt_distance:.0f}m from MRT",
                    latitude=lat,
                    longitude=lng,
                    asking_price=usd_price,
                    bedrooms=infer_bedrooms(price_per_unit),
                    bathrooms=1,
                    sqft=sqft,
                    property_type=infer_property_type(house_age),
                    status="active",
                    disclosures={
                        "house_age_years": house_age,
                        "mrt_distance_meters": mrt_distance,
                        "nearby_convenience_stores": stores,
                        "known_defects": "none",
                        "flood_zone": "no",
                    },
                    neighborhood_data={
                        "convenience_stores": stores,
                        "mrt_distance_m": mrt_distance,
                        "price_per_unit_area_ntd": price_per_unit,
                    },
                )
                db.add(prop)
                count += 1

        await db.commit()
        print(f"Seeded 2 users (buyer + seller) and {count} properties from CSV.")


if __name__ == "__main__":
    asyncio.run(seed())
```

---

## Step 2: Infrastructure Setup

```bash
cd real-estate-agent

# 1. Start PostgreSQL and Redis
docker compose up -d db redis

# 2. Wait for healthy status
docker compose ps

# 3. Configure environment
cp .env.example .env
# Edit .env — set your ANTHROPIC_API_KEY at minimum
```

Required `.env` values:

```
ANTHROPIC_API_KEY=sk-ant-...          # required for agent conversations
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/realestate
REDIS_URL=redis://localhost:6379/0
MARKET_DATA_PROVIDER=mock             # keep mock — CSV provides the listings
ENVIRONMENT=development
```

---

## Step 3: Database Migration + Seed

```bash
# Run migrations
alembic upgrade head

# Seed from CSV (414 properties + buyer + seller)
python scripts/seed_from_csv.py
```

Verify:

```bash
uvicorn main:app --reload &
curl http://localhost:8000/api/properties/ | python -m json.tool | head -40
```

You should see 414 properties with Taipei coordinates and USD prices.

---

## Step 4: Walk Through the Full Operation

### 4A. Browse Properties (Search + Intelligence)

```bash
# List all properties (paginated)
curl "http://localhost:8000/api/properties/"

# Filter by price range matching the buyer's budget
curl "http://localhost:8000/api/properties/?min_price=150000&max_price=400000"

# Get a specific property's detail
curl "http://localhost:8000/api/properties/{PROPERTY_ID}"
```

### 4B. Start a Negotiation

```bash
# Look up user IDs
BUYER_ID=$(curl -s http://localhost:8000/api/users/ | python3 -c "
import sys, json
users = json.load(sys.stdin)
print(next(u['id'] for u in users if u['role'] == 'buyer'))
")

SELLER_ID=$(curl -s http://localhost:8000/api/users/ | python3 -c "
import sys, json
users = json.load(sys.stdin)
print(next(u['id'] for u in users if u['role'] == 'seller'))
")

# Pick a property
PROP_ID=$(curl -s "http://localhost:8000/api/properties/?min_price=200000&max_price=300000" | \
  python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# Start negotiation
curl -X POST http://localhost:8000/api/negotiations/ \
  -H "Content-Type: application/json" \
  -d "{
    \"property_id\": \"$PROP_ID\",
    \"buyer_id\": \"$BUYER_ID\",
    \"seller_id\": \"$SELLER_ID\"
  }"
```

Save the returned `negotiation_id`.

### 4C. Submit Offers (Triggers Agent Negotiation)

The offer and accept endpoints use **query parameters** (not JSON body):

```bash
NEG_ID="<negotiation_id from above>"

# Buyer's opening offer (e.g., 9% below asking)
curl -X POST "http://localhost:8000/api/negotiations/$NEG_ID/offer?offer_price=210000&from_role=buyer&message=Opening+offer"
```

Response shows the state machine in action:
```json
{
  "negotiation_id": "...",
  "new_status": "offer_pending",
  "round": 1,
  "offer_price": 210000.0,
  "deadline_at": "2026-03-20T...",    // 48h from now
  "analysis": { "status": "insufficient_data" }
}
```

This triggers the **NegotiationEngine**:
1. Validates offer via **Guardrails** (must be >= 50% of asking)
2. Creates an `Offer` record
3. Transitions state: `IDLE` -> `OFFER_PENDING`
4. Sets a 48-hour deadline
5. Records a `DomainEvent`
6. Publishes to Redis pub/sub channel `negotiation:{id}`

### 4D. Counter-Offer Flow (Multi-Round)

```bash
# Seller counters at $225k
curl -X POST "http://localhost:8000/api/negotiations/$NEG_ID/offer?offer_price=225000&from_role=seller&message=Counter+offer"

# Buyer counters at $218k
curl -X POST "http://localhost:8000/api/negotiations/$NEG_ID/offer?offer_price=218000&from_role=buyer&message=Final+counter"
```

After round 2+, the response includes **ZOPA analysis**:
```json
{
  "analysis": {
    "round": 3,
    "spread_percent": 6.7,
    "offer_history": [218000.0, 225000.0, 210000.0]
  }
}
```

**What happens at each round:**
- `round_count` increments
- State alternates: `OFFER_PENDING` <-> `COUNTER_PENDING`
- At **round 5+**: ZOPA detection activates — if spread <= 3%, suggests midpoint
- At **round 5+ with spread > 10%**: auto-broker mediation triggered
- At **round 10+**: auto-escalation to `ESCALATED` state

### 4E. Accept and Close

```bash
# Seller accepts at the midpoint price
curl -X POST "http://localhost:8000/api/negotiations/$NEG_ID/accept?from_role=seller&final_price=220000"
```

State progression after acceptance:
```
ACCEPTED -> CONTRACT_PHASE (72h deadline)
         -> INSPECTION     (10-day deadline)
         -> CLOSING         (30-day deadline)
         -> CLOSED
```

### 4F. View the Full Event Trail

```bash
# All domain events for this negotiation
curl "http://localhost:8000/api/negotiations/$NEG_ID/events"
```

Returns the append-only event sourcing trail — every state change, offer, counter, acceptance.

### 4G. Check Negotiation State

```bash
curl "http://localhost:8000/api/negotiations/$NEG_ID"
```

Returns: current status, round count, deadline, final price (if closed).

---

## Step 5: Intelligence System (MiroFish Reports)

```bash
# Request a market intelligence report for the buyer
curl -X POST http://localhost:8000/api/reports/generate \
  -H "Content-Type: application/json" \
  -d '{"user_id": "'$BUYER_ID'"}'
```

This triggers the intelligence pipeline:
1. **Seed Assembly** (`intelligence/seed_assembly.py`) compiles a 5-section document:
   - Investor profile (budget, risk tolerance, timeline)
   - Local market context (median price, inventory from MockMarketDataProvider)
   - Decision framework template
   - Top 30 active listings (from the CSV-seeded properties, enriched with neighborhood data)
   - Platform rules
2. **MiroFish Client** submits the seed to the simulation API (requires MiroFish running on `:5001`)
3. Report status can be polled:

```bash
REPORT_ID="<from generate response>"
curl "http://localhost:8000/api/reports/status/$REPORT_ID"
curl "http://localhost:8000/api/reports/$REPORT_ID"
```

> **Note**: MiroFish is an external simulation service. Without it running, reports will remain in `pending` status. The seed assembly and queueing still execute.

---

## Step 6: Real-Time WebSocket (Frontend)

```bash
# Start frontend
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

On the **NegotiationPage**, connect to a negotiation to see real-time WebSocket events as offers and counter-offers flow through the system.

On the **SearchPage**, view all 414 CSV-seeded properties on the MapLibre map (clustered by location in the Taipei region).

---

## Step 7: Run the Agent Conversation Loop (Full AI)

With `ANTHROPIC_API_KEY` set, the **Orchestrator** routes natural-language messages to role-based agents:

```bash
# Send a message as the buyer agent
curl -X POST http://localhost:8000/api/agent/message \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "'$BUYER_ID'",
    "role": "buyer",
    "message": "I am looking for a property near an MRT station, under $300k, with low house age."
  }'
```

The **BuyerAgent** will:
1. Use `search_properties` tool to query the DB (filtered from your CSV data)
2. Use `analyze_neighborhood` tool for nearby amenities (via TomTom or mock)
3. Use `get_comps` for comparable sales
4. Recommend properties and suggest an offer strategy (start 5-12% below asking)

Similarly for the seller:

```bash
curl -X POST http://localhost:8000/api/agent/message \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "'$SELLER_ID'",
    "role": "seller",
    "message": "How should I price my property? I want to sell within 60 days."
  }'
```

---

## System Architecture in Action

```
CSV Dataset (414 records)
        │
        ▼
  seed_from_csv.py ──────► PostgreSQL (properties table)
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   API Endpoints          Orchestrator           Intelligence
   (properties,          (routes to agents)      (seed assembly)
    offers,                    │                       │
    negotiations)              ▼                       ▼
        │              Claude API + Tools         MiroFish Sim
        │              (search, offer,           (market outlook,
        │               analyze, comps)           timing, risk)
        │                      │                       │
        ▼                      ▼                       ▼
   NegotiationEngine    Agent Decisions          Report Storage
   (state machine,      (recorded in DB)         (mirofish_reports)
    ZOPA detection,            │
    timeout rules)             ▼
        │              Domain Events (event sourcing)
        ▼                      │
   Redis Pub/Sub ◄─────────────┘
        │
        ▼
   WebSocket → React Frontend
   (real-time updates, map view, negotiation chat)
```

---

## Key Things to Observe

| What | Where | What to Look For |
|------|-------|------------------|
| Property listing from CSV | `GET /api/properties/` | 414 entries with Taipei coords and USD prices |
| Offer guardrails | `POST .../offer` with < 50% of asking | 400 error — guardrail blocks it |
| State transitions | `GET .../negotiations/{id}` | Status changes: idle → offer_pending → counter_pending → ... |
| ZOPA detection | After round 5, check logs | "convergence detected" when spread <= 3% |
| Auto-escalation | After round 10 | Status becomes `escalated` |
| Timeout enforcement | Wait 48h (or modify `deadline_at` in DB) | State auto-expires |
| Event replay | `GET .../negotiations/{id}/events` | Full ordered history of every action |
| Agent tool ACL | Agent tries unauthorized tool | Blocked before and after Claude API call |
| Circuit breaker | MiroFish down → 5 failures | Client auto-opens circuit, stops calling |
| WebSocket events | Frontend NegotiationPage | Real-time push on each offer/counter |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `alembic upgrade head` fails with import error | Run from `real-estate-agent/` directory, ensure `pip install -e ".[dev]"` completed |
| No properties returned | Run `python scripts/seed_from_csv.py` after migrations |
| Agent returns empty response | Set `ANTHROPIC_API_KEY` in `.env` |
| MiroFish report stuck in `pending` | MiroFish service not running — expected without it |
| WebSocket disconnects | Ensure Redis is running: `docker compose up -d redis` |
| CSV not found | Ensure file is at `~/Downloads/Real estate valuation data set.csv` |
