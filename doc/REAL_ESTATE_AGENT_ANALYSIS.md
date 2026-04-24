# Real Estate Agentic System — Claude Code Implementation Analysis

## 1. Architecture Decomposition: How to Think About This System

Think of this platform as a **microservice-oriented monolith** — analogous to how a modern OS kernel works. You have a **hot path** (the transaction platform — search, offer, negotiate, close) that must be low-latency and always available, and a **cold path** (MiroFish intelligence layer) that's compute-heavy, asynchronous, and eventually consistent. The Seed Assembly Service is the **bus controller** — it bridges user-space data into the simulation kernel.

### System Topology (Mental Model)


```
┌─────────────────────────────────────────────────────────────┐
│  HOT PATH (Transaction Platform)                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  Buyer   │  │  Seller  │  │  Broker  │  ← Claude API    │
│  │  Agent   │  │  Agent   │  │  Agent   │    (per-turn)     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       └──────────────┼──────────────┘                       │
│                      ▼                                      │
│              ┌───────────────┐                               │
│              │ Orchestrator  │  ← State machine, guardrails │
│              └───────┬───────┘                               │
│                      ▼                                      │
│              ┌───────────────┐                               │
│              │  PostgreSQL   │  ← Source of truth            │
│              └───────────────┘                               │
├─────────────────────────────────────────────────────────────┤
│  COLD PATH (MiroFish Intelligence)                          │
│  ┌──────────────┐    ┌───────────────┐    ┌──────────────┐  │
│  │ Seed Assembly │───►│  MiroFish     │───►│ ReportAgent  │  │
│  │ Service       │    │  Simulation   │    │ Output       │  │
│  └──────┬───────┘    │  (25-35 ticks)│    └──────────────┘  │
│         │            └───────────────┘                       │
│   ┌─────┴─────┐           │                                 │
│   │ Zillow    │     ┌─────┴──────┐                          │
│   │ ATTOM     │     │ Ollama     │                          │
│   │ Maps API  │     │ qwen2.5:14b│                          │
│   └───────────┘     └────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### The Processing Pipeline (How Claude Code Should Build This)

Building this in Claude Code is like constructing a **compiler pipeline** — you process in passes, not all at once. Each phase produces artifacts the next phase consumes.

**Pass 1 (Foundation):** Database schema + FastAPI skeleton + env config → outputs a runnable but empty server
**Pass 2 (Single Agent):** Base agent class + Buyer Agent + guardrails → outputs a system that can search and place offers
**Pass 3 (Multi-Agent):** Seller + Broker + Orchestrator + negotiation state machine → outputs a full transaction loop
**Pass 4 (Intelligence):** Seed Assembly + MiroFish Client + report parser → outputs the prediction layer
**Pass 5 (Frontend):** React + Maps + WebSocket + Report Viewer → outputs the user-facing application
**Pass 6 (Integration):** Docker + feedback loops + monitoring → outputs a deployable system

---

## 2. Critical Metrics Beyond the Spec

The spec covers the **what** but leaves several reliability and performance dimensions unaddressed. Here's what you'll want to instrument from the start:

### 2.1 Agent Quality Metrics

| Metric | What It Measures | Why It Matters |
|--------|-----------------|----------------|
| **Tool Call Success Rate** | % of agent tool invocations that return valid data | A Buyer Agent calling `search_properties` and getting empty results repeatedly means your query translation is broken |
| **Reasoning Coherence Score** | Does the agent's `reasoning` field in `agent_decisions` logically connect to the action taken? | LLMs can hallucinate justifications. Periodic human review of the audit log catches drift |
| **Negotiation Convergence Rate** | % of negotiations that reach ACCEPTED vs. WITHDRAWN/ESCALATED | If >40% escalate, your Broker Agent's mediation prompts need tuning |
| **Guardrail Trigger Frequency** | How often each guardrail fires per 100 transactions | Too frequent = agents are poorly calibrated. Too rare = guardrails may not be working |
| **Agent Latency (p50/p95/p99)** | Time from user message to agent response | Claude API latency + tool execution. p99 > 8s = bad UX |
| **Context Window Utilization** | Tokens used per agent turn vs. max context | Negotiation histories grow. If you're hitting 80%+ of context, you need a summarization strategy |

### 2.2 MiroFish Simulation Quality Metrics

| Metric | What It Measures | Why It Matters |
|--------|-----------------|----------------|
| **Simulation Wall Time** | Real time for a 30-tick simulation | Ollama on qwen2.5:14b will be slow. Budget 5-15 min per run |
| **Agent Memory Coherence** | Do agents reference facts from earlier ticks correctly? | Zep's temporal graph can have retrieval failures; stale edges = hallucinated memory |
| **Report Actionability Score** | % of report recommendations that reference specific, real listings | A report saying "consider properties in your price range" is useless. It should name addresses |
| **Clone Outcome Divergence** | How different are strategy clone outcomes from each other? | If all clones converge on the same answer, the simulation isn't actually exploring the strategy space |
| **Seed Freshness** | Time since last market data refresh in the seed | A seed with week-old listings will produce stale recommendations |
| **Prediction Calibration** | After 6-12 months, how did predictions compare to actual market movement? | The long-term credibility metric. Requires post-close feedback loop (Phase 5) |

### 2.3 Infrastructure Metrics

| Metric | What It Measures | Why It Matters |
|--------|-----------------|----------------|
| **API Cost per Transaction** | Claude API tokens consumed across all agents for one deal lifecycle | A negotiation with 8 counter rounds could consume $5-15 in tokens. Track it |
| **API Cost per Report** | Ollama inference time × ticks × agents | MiroFish is compute-bound. Know your per-report cost |
| **Database Query Latency** | p95 for critical queries (listings, offers, negotiations) | PostgreSQL with JSONB columns needs proper indexing on `investment_goals`, `neighborhood_data` |
| **Redis Memory Pressure** | Memory usage for negotiation state + agent cache | Negotiation state is ephemeral but can accumulate if not TTL'd |
| **Zillow/ATTOM Rate Limits** | Calls remaining vs. quota | Seed Assembly can burst API calls. Cache aggressively |

---

## 3. Ideas for Better Application

### 3.1 Comparative Market Heat Map (High Impact, Moderate Effort)

Instead of just showing listings on a map, generate a **heat map overlay** from MiroFish simulation data. Each cell represents a micro-market area, colored by the simulation's predicted price movement direction. Think of it like a **thermal camera for real estate** — buyers see where value is heating up or cooling down, informed by the swarm agents' collective behavior.

Implementation: After each simulation, extract per-neighborhood sentiment from the post-simulation knowledge graph. Aggregate by zip code or census tract. Render as a Leaflet tile layer overlaid on the Google Maps component.

### 3.2 "What-If" Scenario Engine (High Impact, High Effort)

The spec mentions users can re-run simulations with adjusted parameters, but doesn't specify the UX. Build it as a **parameter playground**: sliders for budget (±20%), interest rate assumptions (±1.5%), timeline (30/60/90/180 days), and strategy weights. Each adjustment triggers a delta simulation (not full re-run — just re-evaluate the strategy clones with the modified seed). This is like **branch prediction** in a CPU — you're speculatively executing futures.

### 3.3 Agent Personality Calibration via User Feedback (Medium Impact, Low Effort)

After each negotiation round, let users rate whether the agent's behavior felt appropriate (too aggressive, too passive, just right). Store this in `agent_memory` as preference weights. Over time, the Buyer Agent learns that this particular user wants more aggressive initial offers but gentler counter-offers. This is essentially **online RLHF at the application layer** — you're tuning the system prompt dynamically based on user reward signals.

### 3.4 Deal DNA Fingerprint (Medium Impact, Medium Effort)

For every closed deal, generate a structured "DNA" — a vector encoding the deal's characteristics (price delta from asking, negotiation rounds, days to close, inspection issues, buyer profile type, market conditions at time of close). Store these as embeddings. When a new user enters a negotiation, retrieve the 5 most similar historical deals and surface them as "deals like yours" — showing the user what happened in similar situations. This is a **content-based recommendation system** applied to real estate transactions.

### 3.5 Adversarial Guardrail Testing via MiroFish (Low Effort, Already Designed)

The spec mentions MiroFish can spawn adversarial agents to probe guardrail robustness. Formalize this: run a quarterly "red team simulation" where adversarial agent personas attempt to bypass guardrails (submitting offers above budget, suppressing disclosures, manipulating comps). Log every guardrail trigger and near-miss. This maps directly to your Claudius research methodology — same principle, different domain.

### 3.6 Market Sentiment NLP Layer (Medium Impact, Medium Effort)

Augment the seed document with a sentiment section extracted from local real estate news, Reddit threads (r/realestate, city-specific subs), and Zillow forum posts. Use a lightweight NLP pipeline (even a single Claude call with a structured output schema) to extract market sentiment signals: "bearish on downtown condos," "bullish on suburban SFR." Feed this into the seed's market context section so MiroFish agents reason over qualitative sentiment, not just quantitative data.

### 3.7 Multi-User Simulation Cohorts (High Impact, High Effort, Long-term)

Right now, each MiroFish simulation is per-user. But in reality, buyers compete with each other. A future iteration could run **cohort simulations** where multiple real users' profiles are anonymized and loaded as strategy clones in the same simulation. The output tells each user not just "here's what you should do" but "here's what you should do given that 3 other buyers in your price range are also actively searching." This is the difference between a single-player and multiplayer game — the emergent behavior is richer.

---

## 4. Risk Assessment: What Will Go Wrong

### 4.1 Ollama Performance Bottleneck
**Risk:** qwen2.5:14b on consumer hardware will make 30-tick simulations with 15-20 agents take 15-30 minutes.
**Mitigation:** Implement a job queue (Redis + Celery/ARQ) so simulations run asynchronously. Show users a progress indicator. Cache seeds aggressively — if market data hasn't changed significantly, serve a cached report.

### 4.2 Seed Assembly Fragility
**Risk:** The Seed Assembly Service depends on Zillow API, ATTOM API, and Google Maps API. Any one failing breaks report generation.
**Mitigation:** Build each data source with a fallback strategy. Cache the last successful response per zip code. If Zillow is down, use cached listings + a "data freshness warning" in the report.

### 4.3 Agent Prompt Drift
**Risk:** As you iterate on system prompts, small changes can cascade into dramatically different agent behavior. A Buyer Agent that was "firm but fair" can become "passive" with one wording change.
**Mitigation:** Version your prompts in the `prompts.py` module with semantic versioning. Write regression tests that feed known negotiation scenarios and assert on behavioral outcomes (not exact wording).

### 4.4 Negotiation Deadlock
**Risk:** Two well-tuned agents (Buyer wants low, Seller wants high) can oscillate in a counter-offer loop even under the 10-round cap, producing frustrating user experiences.
**Mitigation:** The Broker Agent should implement a **ZOPA detector** (Zone of Possible Agreement). If the spread between offers narrows to <3% of asking, suggest a split. If it doesn't narrow after 5 rounds, flag the negotiation as likely unresolvable.

---

## 5. Claude Code Build Strategy

### The Right Way to Scaffold This

Don't try to build the whole thing in one Claude Code session. Think of each session as a **Git commit** — atomic, testable, and buildable.

**Session 1:** Project scaffold + database + env config
**Session 2:** Base agent class + Claude API integration + tool registration pattern
**Session 3:** Buyer Agent (full implementation with all tools)
**Session 4:** Guardrails module + unit tests
**Session 5:** Seller Agent + Broker Agent
**Session 6:** Orchestrator + negotiation state machine
**Session 7:** Seed Assembly Service + MiroFish Client
**Session 8:** API endpoints (REST + WebSocket)
**Session 9:** Frontend scaffold + Google Maps integration
**Session 10:** Intelligence Report viewer + Strategy Comparison UI
**Session 11:** Docker compose + deployment config
**Session 12:** Integration tests + red team simulation setup

Each session should produce a working, testable increment. The setup file below bootstraps Session 1.
