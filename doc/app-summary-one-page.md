# Real Estate Agentic Platform - One-Page Summary

## What It Is
An AI-powered satei-to-close SaaS platform for Tokyo real estate brokerages (不動産仲介). Combines a FastAPI backend, React frontend, and multi-agent AI system to help brokers win listings, set optimal asking prices, and coach negotiation strategy.

## Who It Is For
- Primary persona: **brokerage agent (不動産仲介営業担当者)** — mid-size and proptech-native Tokyo firms using AI-assisted valuation and negotiation coaching to differentiate against major incumbents.
- Secondary: investor-focused users managing portfolios (legacy surface, retained but no longer primary go-to-market).

## What It Does
- **Satei Comp Grid (査定コンプグリッド):** Automated comparable-based valuation with editable hedonic adjustment grid. Pulls REINFOLIB transaction data, applies adjustments for age/area/walk-time/construction, produces defensible satei price. Reduces satei time from ~180 min to ~10 min.
- **Price-vs-Probability Curve (価格帯別成約確率カーブ):** Monte Carlo simulation producing settlement probability distributions — "list at X yen → Y% chance of closing within 30/60/90/180 days." Answers the asking-price question with data, not intuition.
- **Negotiation Strategy Coach (交渉戦略コーチ):** Multi-agent negotiation simulation repositioned as a broker coaching tool. Input client reservation price + counterparty profile → explore scenarios, concession ladders, ZOPA analysis before real negotiations.
- Retains investor portfolio management, underwriting, and strategy projection surfaces.

## How It Works (Repo-Evidenced)
- **Frontend:** React + TypeScript + Vite (`frontend/src/*`) with pages for satei, negotiation coaching, investment analysis, portfolio, and profile.
- **API layer:** FastAPI routers mounted in `main.py` (`/api/satei`, `/api/price-probability`, `/api/properties`, `/api/reports`, `/api/simulation`, etc.).
- **Core services:** satei engine (`services/satei_engine.py`), price probability (`services/price_probability.py`), negotiation coach (`services/negotiation_coach.py`), REINFOLIB signal providers (`services/signal_providers/`), analyst council (`agent/analyst_council.py`).
- **Data layer:** SQLAlchemy models + async sessions (`db/models.py`, `db/database.py`), Alembic migrations, Redis-backed pub/sub and cache.
- **Typical flow:** Broker inputs property → satei engine pulls comps + applies adjustments → price-probability curve generated → negotiation coach available for scenario rehearsal.

## How to Run (Minimal)
1. `docker compose -f ~/docker-shared-services.yml up -d postgres redis && bash scripts/init-shared-db.sh`
2. `pip install -e ".[dev]"`
3. `cp .env.example .env`
4. `alembic upgrade head && python scripts/seed_properties.py`
5. `uvicorn main:app --reload`
6. (Frontend) `cd frontend && npm install && npm run dev`

## Competitive Positioning
- Direct competitors (SRE AI査定CLOUD, Collabit AI査定プロ, Sumasate) are valuation-only tools.
- **No identified product combines hedonic valuation + price-probability curves + negotiation simulation** — this triad is whitespace as of June 2026.
- See `doc/BROKERAGE_PITCH.md` for full competitive analysis and go-to-market strategy.
