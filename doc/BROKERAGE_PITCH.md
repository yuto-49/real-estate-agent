# Real Estate Agentic: AI-Powered Satei-to-Close SaaS for Tokyo Real Estate Brokerages
# 査定から成約まで — 不動産仲介向けAI査定・価格戦略・交渉コーチングSaaS

**The only platform combining hedonic valuation + settlement-price-vs-probability curves + multi-agent negotiation simulation**

---

## The Problem: Three Decisions That Make or Break a Brokerage

Tokyo's residential brokerage market is dominated by five high-volume incumbents. The critical competitive advantage is winning listings (媒介獲得) — and that comes down to three decisions:

1. **The satei/valuation decision (査定)** — Every listing pitch requires it. Currently 180 minutes of manual REINS comp work. The broker who delivers a faster, more defensible satei wins the listing.

2. **The asking-price decision** — Mispricing is the #1 cause of slow sales. List too high → stale listing → price cuts → seller loses trust. List too low → money left on the table. Currently pure intuition.

3. **The accept/counter/reservation-price decision** — When offers come in, brokers advise clients on whether to accept, counter, or wait. Currently based on gut feel and experience, with no way to rehearse scenarios.

---

## The Solution: AI That Compresses 180 Minutes to 10 — Then Goes Further

Three integrated tools that no competitor offers together:

### Tool 1: Satei Comp Grid (査定コンプグリッド)
- Pull REINFOLIB transaction comps automatically
- Apply hedonic adjustments (age, floor area, walk time, construction type, floor level) in an editable spreadsheet grid
- Broker overrides any adjustment — the system recomputes instantly
- Output: defensible satei price with confidence band + professional satei document
- **Time savings: 180 min → ~10 min per satei**

### Tool 2: Price-vs-Probability Curve (価格帯別成約確率カーブ)
- Given the satei value, show: "list at X yen → Y% probability of closing within 30/60/90/180 days"
- Powered by Monte Carlo simulation calibrated against historical REINFOLIB transaction data
- Interactive chart — slide the asking price, watch probabilities shift in real time
- **Answers the seller's #1 question: "should I list high or sell fast?"**

### Tool 3: Negotiation Strategy Coach (交渉戦略コーチ)
- Multi-agent simulation: input your client's reservation price, counterparty profile, property context
- AI generates counterparty personas and runs negotiation scenarios
- Output: recommended opening position, concession ladder, walk-away points, ZOPA analysis
- **Positioned as coaching/rehearsal, not an oracle** — lets junior agents perform like veterans

---

## Target Market & Competitive Landscape

### Industry Structure
- Japanese residential brokerage runs on REINS (legally mandated listing exchange)
- Commission capped at 3% + ¥60,000 (+tax) per side; dual-agency (両手) yields ~6%
- Satei (price assessment) is the key listing-pitch instrument under 宅地建物取引業法
- Satei is explicitly NOT 不動産鑑定 (appraisal) — no licensing barrier for AI satei tools

### Target Companies (First Wave — Mid-Size & Proptech-Native)

| Company | Size | Why They Fit |
|---|---|---|
| **Open House / オープンハウス** | Group sales ¥1.336T; ~2,875 employees | Aggressive, sales-driven, tech-adopting, high productivity |
| **SRE Realty** (ex-Sony RE) | Sony group, AI-native | Single-agency (片手) model aligns with seller-maximizing tools; possible co-dev partner |
| **GA technologies / RENOSY** | Revenue ¥189.8B; TSE Growth | Most likely fast adopter; already deploying AI agents |
| **Mid-size & franchise** (Century 21 Japan, ERA, rail-affiliated) | Hundreds of offices | Faster decisions, hungry for differentiation vs big incumbents |

### Target Companies (Second Wave — Enterprise)

| Company | Size | Why |
|---|---|---|
| **Tokyu Livable / 東急リバブル** | ¥2,231.1B volume (#1); ~200+ stores | Most tech-forward incumbent, already markets "AI査定" |
| **Mitsui Fudosan Realty / 三井のリハウス** | 38,103 deals FY24 (#1 by count); 277 stores | Largest deal count = most satei volume to accelerate |
| **Sumitomo Fudosan STEP** | ¥1,392.8B volume; 31,502 deals | Man-to-man model → per-seat licensing maps cleanly |
| **Nomura Real Estate Solutions** | ¥1,221.8B volume; ~10,200 deals | High per-deal price → outsized value from pricing tools |

### Competitive Products

**Layer 1 — Consumer AVM / lead-gen** (HowMa, IESHIL, おうちクラベル): Free to consumers, monetized by referrals. Not B2B tools.

**Layer 2 — B2B satei SaaS** (our direct competitors):

| Product | What It Does | What It Doesn't Do |
|---|---|---|
| SRE AI査定CLOUD | AI satei document, "180 min → 10 min" | No price-probability curve, no negotiation simulation |
| Collabit AI査定プロ | AI satei, ¥12,800/month entry | No probability curve, no negotiation coaching |
| Sumasate | Rent AVM, ~1,800 firms, from ¥21,780/month | Rent only, no sale price satei, no simulation |
| ITANDI PropoCloud | Satei workflow | No AI valuation, no simulation |
| Leeways Gate. | AVM for 300+ brokerages | No negotiation tools |

**Layer 3 — Global** (HouseCanary, Pactum AI): HouseCanary does enterprise AVM; Pactum does autonomous negotiation but in procurement, not real estate.

### What Is Novel
**No identified product — Japanese or global — packages hedonic valuation + price-probability curves + negotiation role-play simulation together.** This specific triad is whitespace as of June 2026.

---

## Business Model

### Pricing (benchmarked to competitors)

| Tier | Price | What's Included |
|---|---|---|
| **Starter** | ¥13,000/month/agent | Satei Comp Grid (unlimited), 10 price-probability curves/month |
| **Professional** | ¥19,800/month/agent | All tools unlimited, negotiation coach, satei document export |
| **Enterprise** | Custom | White-label, API access, dedicated support, REINS direct integration |

### Unit Economics

| Metric | Value |
|---|---|
| Cost per satei computation | ~¥2 (4x Claude Haiku calls) |
| Cost per price-probability curve | ~¥15 (100 Monte Carlo simulations) |
| Cost per negotiation coaching session | ~¥20 (multi-agent simulation) |
| Infrastructure (PostgreSQL + Redis + compute) | ~¥7,500/month |
| **Gross margin at 50 agents on Professional** | **~92%** |

### Value Proposition Math
- Average brokerage commission per deal: ~¥1.8M (¥60M property x 3%)
- If this tool wins 1 additional listing per agent per quarter: ¥1.8M incremental revenue
- Tool cost: ¥19,800/month x 3 months = ¥59,400
- **ROI: 30x per additional listing won**

---

## What's Built Today

| Capability | Status |
|---|---|
| Property listing ingestion + search | Live |
| REINFOLIB transaction data integration | Live |
| Rent comp validation engine | Live |
| Multi-agent negotiation simulation (8-state machine) | Live |
| Monte Carlo stress testing engine | Live |
| 4-persona AI analyst council | Live |
| Market signal pipeline (REINFOLIB, e-Stat) | Live |
| Domain event audit trail (宅建業法 compliance) | Live |
| Supabase JWT authentication | Live |
| React frontend (8 pages) | Live |

### What's Next (Tier 1 — see TIER1_IMPLEMENTATION_PLAN.md)

| Feature | Timeline |
|---|---|
| Satei Comp Grid with editable adjustment grid | Weeks 1-2 |
| Price-vs-Probability Curve | Weeks 3-4 |
| Negotiation Strategy Coach | Week 5 |

---

## Go-to-Market Recommendations

1. **Target mid-size and proptech-native first**, not the big 5. SRE Realty, GA technologies, Open House, franchise chains decide faster and need differentiation.
2. **Lead with satei + 媒介獲得 value prop** (proven willingness-to-pay), use negotiation simulator + probability curve as unique differentiator no competitor offers.
3. **Run a paid pilot with one single-agency firm** to prove: "satei time cut" and "媒介獲得 rate lift" — the two numbers Japanese brokerage buyers respond to.
4. **Pursue enterprise only after pilot yields referenceable ROI case** — Tokyu Livable is the most receptive given existing AI-査定 marketing.

### Adoption Barriers to Address
- Conservative industry culture → start with tech-forward firms
- Trust in AI valuations → editable grid puts broker in control, AI assists
- 両手 (dual-agency) incentive tension → seller-maximizing tools natural fit for single-agency firms like SRE
- Japanese-language UX → platform already Japan-native (ward codes, construction types, station walk times)

---

## Technology Architecture

```
React 18 + Vite (Frontend)
        |
FastAPI + Python 3.11 (Backend)
        |
   +---------+---------+---------+
   |         |         |         |
 Satei     Price-Prob  Negotiation  Auth
 Comp Grid  Curve      Coach       (Supabase JWT)
 (Claude   (Monte     (Multi-agent
  Haiku)    Carlo)     simulation)
   |         |         |
   +---------+---------+
        |
PostgreSQL 16 + Redis 7
(REINFOLIB + e-Stat data integrations)
```

**Key design principles:**
- **AI is the analyst, math is the engine, the broker stays in control.** Only ~4 Claude calls per satei. Everything else is deterministic math. No hallucination risk in financial projections.
- **Async-first.** All database, Redis, and API calls are non-blocking.
- **Japan-native data model.** Ward codes, construction types (木造/軽量鉄骨/鉄骨/RC/SRC), seismic classifications, station walk times — built in from day one, not retrofitted.

---

## Caveats
- Volume/deal-count figures are FY2024-2025 from 不動産流通推進センター statistics and company IR
- "No product combines all three layers" is based on extensive search as of June 2026; stealth products may exist
- Pricing for SRE AI査定CLOUD and Leeways Gate. is not publicly published; benchmarks from Collabit and Sumasate
- LLM negotiation simulators have documented rationality limitations; positioned as coaching, not automated dealmaking

---

*Platform: Real Estate Agentic*
*Status: Post-MVP, building Tier 1 brokerage features*
*Generated June 14, 2026*
