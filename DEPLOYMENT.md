# Deployment Architecture — Real Estate Agentic Platform

This document maps every layer of the platform to its recommended cloud hosting service, with cost analysis for LLM providers. The goal is a production-grade deployment that is operationally sound and cost-efficient at scale.

---

## Architecture Layers at a Glance

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER                   │  PRIMARY SERVICE       │  FALLBACK / ALT     │
├──────────────────────────┼────────────────────────┼─────────────────────┤
│  Frontend (React SPA)    │  Vercel                │  Cloudflare Pages   │
│  API Gateway             │  Railway               │  Render / Fly.io    │
│  FastAPI Workers         │  Railway (container)   │  Fly.io             │
│  PostgreSQL              │  Neon (serverless)     │  Supabase           │
│  Redis (cache + pub/sub) │  Upstash Redis         │  Railway Redis      │
│  LLM – Agents            │  DeepSeek API          │  Gemini Flash 2.0   │
│  LLM – Simulations       │  Groq (Llama 3.3 70B)  │  Together AI        │
│  Maps (geocoding)        │  TomTom Maps           │  Nominatim (self)   │
│  MiroFish Engine         │  Fly.io (sidecar)      │  Self-hosted VPS    │
│  Market Data             │  ATTOM / RapidAPI      │  Mock provider      │
│  Observability           │  Grafana Cloud (free)  │  Axiom              │
│  CDN / Edge              │  Cloudflare (free)     │  Vercel Edge        │
│  Secrets / Config        │  Doppler               │  Railway env vars   │
└──────────────────────────┴────────────────────────┴─────────────────────┘
```

---

## Layer-by-Layer Breakdown

### 1. Frontend — React 18 + TypeScript + Vite

**Service: [Vercel](https://vercel.com)**

Vercel is the natural fit for Vite/React SPAs. Automatic preview deployments per PR, global CDN, and zero-config for Vite.

```
Pricing (Free Hobby → Pro $20/mo):
  - Free: 100 GB bandwidth, unlimited deployments
  - Pro: 1 TB bandwidth, password-protected previews, team access
```

**Deployment steps:**
```bash
# Connect GitHub repo → Vercel auto-detects Vite
# Set env var:
VITE_API_BASE_URL=https://api.your-domain.com
VITE_WS_URL=wss://api.your-domain.com
```

**Alternative: [Cloudflare Pages](https://pages.cloudflare.com)** — free tier is more generous on bandwidth; pairs well if already using Cloudflare for DNS/CDN.

---

### 2. Backend API — FastAPI + Uvicorn (ASGI)

**Service: [Railway](https://railway.app)**

Railway natively runs Docker containers (your existing `Dockerfile`), supports multiple workers, environment variable management, and auto-deploy from GitHub. No Kubernetes needed for this workload.

```
Pricing:
  - Hobby: $5/mo credit (essentially free for dev)
  - Pro: Usage-based ~$0.000463/GB-hr RAM + $0.000231/vCPU-hr
  - Typical cost for 2 replicas × 512 MB RAM: ~$10-15/mo
```

**Production command (matches docker-compose.prod.yml):**
```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000",
     "--workers", "4", "--loop", "uvloop"]
```

**Alternative: [Fly.io](https://fly.io)** — better for multi-region deployment (WebSocket affinity important for `/ws/negotiation/{id}`); free allowance includes 3 shared VMs.

**Alternative: [Render](https://render.com)** — simpler than Railway, good for single-region, free tier has cold starts.

> **Note on WebSockets:** Ensure your hosting provider supports persistent connections (Railway and Fly.io both do). Vercel Functions do NOT support WebSockets — the FastAPI backend must live on Railway/Fly.io.

---

### 3. PostgreSQL

**Service: [Neon](https://neon.tech) (serverless PostgreSQL 16)**

Neon is a serverless Postgres that autoscales to zero when idle, matches your async SQLAlchemy setup, and supports branching (great for staging environments that mirror prod schema).

```
Pricing:
  - Free: 0.5 GB storage, 1 project, autoscales to zero
  - Launch: $19/mo — 10 GB storage, autoscale, no cold-start on active plans
  - Scale: $69/mo — 50 GB, read replicas, point-in-time restore
```

**Connection string format (matches config.py):**
```
postgresql+asyncpg://user:password@ep-xxx.us-east-1.aws.neon.tech/realestate?sslmode=require
```

**Alternative: [Supabase](https://supabase.com)** — free tier includes 500 MB, built-in auth/storage; slightly more overhead but good for teams needing a dashboard UI.

**Alternative: [PlanetScale](https://planetscale.com)** — MySQL only, not suitable for JSONB columns used in this project.

> **Schema migration** is handled by Alembic. On each deploy, run:
> ```bash
> alembic upgrade head
> ```

---

### 4. Redis (Cache, Pub/Sub, Job Queue)

**Service: [Upstash Redis](https://upstash.com)**

Upstash is serverless Redis with per-request pricing, which fits this platform's mixed-use pattern (geocache + negotiation pub/sub + rate limiting). No idle cost.

```
Pricing:
  - Free: 10,000 commands/day, 256 MB
  - Pay-as-you-go: $0.2 per 100K commands
  - Fixed: $10/mo → 1M commands/day, 1 GB
```

**Connection (matches config.py):**
```
REDIS_URL=rediss://default:password@us1-xxx.upstash.io:6380
```

**Alternative: [Railway Redis](https://railway.app)** — if already on Railway, add a Redis service in the same project for lowest latency (same internal network, no SSL overhead on hot path).

> **Important:** Upstash does not support Redis Streams natively at full fidelity. If the job queue in `services/job_queue.py` uses `XADD`/`XREAD`, use Railway Redis instead.

---

## LLM Provider Analysis

This platform makes three distinct types of LLM calls, each with different requirements:

| Use Case | Calls Per Session | Latency Sensitivity | Reasoning Depth |
|---|---|---|---|
| Agent conversations (buyer/seller/broker) | ~10 tool rounds × N negotiations | Medium (real-time chat) | High (multi-step) |
| Social simulation opinion rounds | Hundreds per run | Low (batch async) | Medium |
| Persona generation | ~50 per batch | Low (one-shot) | Low |

---

### Current Provider: Anthropic Claude

The codebase hardcodes `claude-sonnet-4-6` (`agent/base_agent.py`). Claude Sonnet 4.6 is excellent for complex multi-step agent reasoning but is among the more expensive frontier models.

```
Claude Sonnet 4.6 pricing (approximate):
  Input:  $3.00 / 1M tokens
  Output: $15.00 / 1M tokens
```

---

### Recommended: DeepSeek API

**[DeepSeek](https://platform.deepseek.com)** is the strongest cost-reduction option for agent reasoning.

```
DeepSeek-V3 pricing:
  Input:  $0.27 / 1M tokens (cache hit: $0.07)
  Output: $1.10 / 1M tokens
  → ~11× cheaper than Claude Sonnet for input tokens

DeepSeek-R1 pricing (reasoning model):
  Input:  $0.55 / 1M tokens
  Output: $2.19 / 1M tokens
  → Strong multi-step reasoning, suitable for BrokerAgent
```

**Model mapping:**
- `BuyerAgent` / `SellerAgent`: `deepseek-chat` (DeepSeek-V3) — fast, cheap, sufficient
- `BrokerAgent` (contract drafting, compliance): `deepseek-reasoner` (DeepSeek-R1) — complex reasoning
- `SocialSimulator` opinion rounds: `deepseek-chat` — high volume, low complexity

**Integration:** DeepSeek exposes an OpenAI-compatible API. Swap the client in `agent/base_agent.py`:

```python
# Before (Anthropic SDK)
from anthropic import AsyncAnthropic
client = AsyncAnthropic(api_key=settings.anthropic_api_key)

# After (OpenAI-compatible — works with DeepSeek, Groq, Together AI)
from openai import AsyncOpenAI
client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url="https://api.deepseek.com"
)
```

> **Caution:** DeepSeek is based in China. Review your data residency requirements. Avoid sending PII or sensitive financial data if operating under GDPR or CCPA with EU/CA users. Use DeepSeek for simulation/analysis and keep user-facing agent calls on Anthropic if needed.

---

### Best Cost Alternative: Google Gemini Flash 2.0

**[Google AI Studio / Vertex AI](https://ai.google.dev)**

Gemini Flash 2.0 is the best cost-per-quality alternative for high-volume calls and is not subject to the same data residency concerns as DeepSeek.

```
Gemini 2.0 Flash pricing:
  Input:  $0.10 / 1M tokens (≤128K context)
  Output: $0.40 / 1M tokens
  → ~30× cheaper than Claude Sonnet for input tokens
  → ~3× cheaper than DeepSeek-V3

Gemini 2.0 Flash-Lite:
  Input:  $0.075 / 1M tokens
  Output: $0.30 / 1M tokens
  → Best for high-volume social simulation rounds
```

**Use case fit:**
- `SocialSimulator` opinion rounds (hundreds per run): Gemini Flash-Lite
- `PersonaGenerator` batch calls: Gemini Flash-Lite
- `BuyerAgent` / `SellerAgent` (live negotiation): Gemini Flash 2.0
- `BrokerAgent` (complex contracts): DeepSeek-R1 or Claude Sonnet

**Integration via OpenAI-compatible endpoint:**
```python
client = AsyncOpenAI(
    api_key=settings.google_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
model = "gemini-2.0-flash"
```

---

### Third Option: Groq (for Simulation Throughput)

**[Groq](https://console.groq.com)** uses custom LPU hardware for extremely fast inference — ideal for the `BatchSimulator` and `SocialSimulator` where you run many parallel calls.

```
Groq pricing (Llama 3.3 70B):
  Input:  $0.59 / 1M tokens
  Output: $0.79 / 1M tokens
  Speed:  ~900 tokens/second (vs ~50-80 for most providers)
  → Simulation that takes 60s on Claude takes ~5s on Groq
```

**Best for:** `services/social_simulator.py` and `services/batch_simulator.py` where latency directly controls wall-clock simulation time.

---

### LLM Cost Comparison Summary

| Provider | Model | Input $/1M | Output $/1M | Best For |
|---|---|---|---|---|
| Anthropic | Claude Sonnet 4.6 | $3.00 | $15.00 | Highest quality, complex agents |
| DeepSeek | DeepSeek-R1 | $0.55 | $2.19 | BrokerAgent reasoning |
| DeepSeek | DeepSeek-V3 | $0.27 | $1.10 | Buyer/SellerAgent (general) |
| Google | Gemini Flash 2.0 | $0.10 | $0.40 | Live negotiation chat |
| Google | Gemini Flash-Lite | $0.075 | $0.30 | Social sim / persona gen |
| Groq | Llama 3.3 70B | $0.59 | $0.79 | Batch sim throughput (fast) |
| Together AI | Llama 3.1 70B | $0.54 | $0.54 | Budget fallback |

**Recommended hybrid strategy:**
```
BrokerAgent (contracts, compliance):      DeepSeek-R1  (~$0.55 input)
BuyerAgent / SellerAgent (live chat):     Gemini Flash 2.0 (~$0.10 input)
SocialSimulator opinion rounds (batch):   Gemini Flash-Lite (~$0.075 input)
PersonaGenerator (one-shot):              Gemini Flash-Lite (~$0.075 input)
BatchSimulator (parallel scenarios):      Groq Llama 3.3 70B (fastest wall-time)
```

This hybrid reduces LLM cost by approximately **25-40× vs full Claude Sonnet usage** while maintaining reasoning quality where it matters (broker/compliance layer).

---

### Config Changes Required

Add to `config.py`:
```python
# LLM Providers
deepseek_api_key: str = ""
google_api_key: str = ""
groq_api_key: str = ""

# Per-agent model routing
broker_llm_provider: str = "deepseek"   # deepseek | anthropic
buyer_llm_provider: str = "google"      # google | anthropic
simulation_llm_provider: str = "groq"   # groq | google | anthropic
```

---

## External APIs

### Maps — TomTom

Already integrated (`services/maps.py`). Free tier: 2,500 requests/day.

**Scaling:** TomTom Pro plan at ~$0.42/1,000 requests for geocoding. For a production platform, cache aggressively using the existing `geohash2`-keyed Redis cache (`services/maps.py`).

**Alternative:** [Nominatim](https://nominatim.org) (self-hosted, OpenStreetMap) for zero API cost, or [Mapbox Geocoding](https://www.mapbox.com) ($0.50/1,000 requests, 100K free/mo).

### Market Data — ATTOM / RapidAPI

The `market_data_provider = "zillow"` config path exists but is not yet implemented (falls back to mock). For production:

- **ATTOM Data API** — comprehensive property records, tax data, comparables. Pricing: $299/mo for 10,000 property lookups.
- **RapidAPI / Zillow** — listing data via RapidAPI marketplace at ~$0.001/request.
- **Rentcast** — rental market data API, $29/mo for 5,000 calls; good for workforce housing rent analysis.

---

## Observability

### Service: [Grafana Cloud](https://grafana.com/products/cloud/)

Free tier includes:
- 10K metrics series (Prometheus scrape from `/metrics`)
- 50 GB logs (Loki)
- 50 GB traces (Tempo)
- 3 users

**Integrate with `structlog`** by adding a Loki log shipper (Promtail or Alloy agent on Railway).

**Alternative: [Axiom](https://axiom.co)** — simpler setup, free tier 500 GB ingest/mo.

---

## Full Stack Cost Estimate

### Development / MVP (low traffic)

| Service | Plan | Monthly Cost |
|---|---|---|
| Vercel (frontend) | Hobby | $0 |
| Railway (API, 1 replica) | Hobby | $5 |
| Neon (PostgreSQL) | Free | $0 |
| Upstash Redis | Free | $0 |
| DeepSeek / Gemini (LLM) | Pay-per-use | ~$5-20 |
| TomTom Maps | Free | $0 |
| Grafana Cloud | Free | $0 |
| **Total** | | **~$10-25/mo** |

### Production (moderate traffic, 100 active users/day)

| Service | Plan | Monthly Cost |
|---|---|---|
| Vercel (frontend) | Pro | $20 |
| Railway (API, 2 replicas) | Pro usage | ~$25 |
| Neon (PostgreSQL) | Launch | $19 |
| Railway Redis | Pro | ~$10 |
| DeepSeek + Gemini (LLM) | Pay-per-use | ~$50-150 |
| TomTom Maps | Pay-per-use | ~$10 |
| ATTOM / Rentcast | Starter | $29-299 |
| Grafana Cloud | Free | $0 |
| **Total** | | **~$163-523/mo** |

> LLM cost is the dominant variable. With full Claude Sonnet, the same usage would cost ~$500-2,000/mo in LLM alone. The hybrid DeepSeek + Gemini Flash strategy reduces this to ~$50-150/mo.

---

## Deployment Checklist

```
Infrastructure:
  [ ] Provision Neon PostgreSQL, copy connection string to Doppler
  [ ] Provision Upstash Redis, copy URL to Doppler
  [ ] Create Railway project, link GitHub repo, add Doppler env integration
  [ ] Connect Vercel to GitHub frontend/ directory

Database:
  [ ] Run: alembic upgrade head (via Railway deploy command)
  [ ] Run: python scripts/seed_properties.py (one-time)

Secrets (via Doppler or Railway env vars):
  [ ] ANTHROPIC_API_KEY (or DEEPSEEK_API_KEY / GOOGLE_API_KEY)
  [ ] DATABASE_URL (Neon connection string, asyncpg format)
  [ ] REDIS_URL (Upstash connection string)
  [ ] TOMTOM_API_KEY
  [ ] MIROFISH_MODE=mock (until MiroFish is deployed)

Networking:
  [ ] Set CORS allowed origins in main.py to Vercel domain
  [ ] Set VITE_API_BASE_URL and VITE_WS_URL in Vercel env vars
  [ ] Enable Cloudflare proxy for custom domain (TLS termination)

Observability:
  [ ] Configure structlog to emit JSON to stdout (Railway captures it)
  [ ] Set up Grafana Cloud Loki scrape from Railway log drain

Smoke tests:
  [ ] GET /health → 200
  [ ] POST /api/agent/message with buyer role
  [ ] WS /ws/negotiation/test → connects
```

---

## MiroFish Engine

MiroFish (`intelligence/mirofish_client.py`) is currently designed to call an external HTTP service at `config.mirofish_api_url`. In production:

- **Mock mode** (`MIROFISH_MODE=mock`): runs entirely in-process, no external call needed. Suitable for MVP.
- **Live mode**: deploy MiroFish as a separate service on **Fly.io** or **Railway** (second service in same project), set `MIROFISH_API_URL` to its internal URL for zero-egress cost.

The circuit breaker (5 failures → 60s open) and retry logic (3 attempts, exponential backoff) are already implemented and will handle transient failures gracefully.
