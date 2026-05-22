# Agent Architecture

How the multi-agent system actually works end-to-end. Read this before touching
`agent/`, the orchestrator, tool handlers, or the negotiation engine.

> **Pure-Python projections** under `domain/` are a parallel, side-effect-free
> layer (see `SOCIAL_SIMULATION_IMPLEMENTATION.md`). This doc is about the
> **live agent runtime** that talks to Claude and persists state.

---

## 1. Big Picture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              REQUEST PATH                                    │
│                                                                              │
│  HTTP/WS request ──► FastAPI router (api/) ──► AgentOrchestrator             │
│        │                                            │                        │
│        │                                            ▼                        │
│        │                                ┌───────────────────────┐            │
│        │                                │   route_message()     │            │
│        │                                │   start_negotiation() │            │
│        │                                └───────────┬───────────┘            │
│        │                                            │                        │
│        │                       ┌────────────────────┼────────────────────┐   │
│        │                       │                    │                    │   │
│        ▼                       ▼                    ▼                    ▼   │
│   Correlation ID         BuyerAgent           SellerAgent          BrokerAgent│
│   middleware/auth.py     BaseAgent            AssistantAgent        + tools   │
│   middleware/correlation                                                     │
└────────────────────┬──────────────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         AGENT TURN (BaseAgent.process_message)               │
│                                                                              │
│   1. Build messages [system_prompt, user_message]                            │
│   2. Filter tools by AgentRole (tool_acl.TOOL_PERMISSIONS — frozen)          │
│   3. Call Claude (Anthropic SDK, model = claude-sonnet-4-6)                  │
│   4. If response has tool_use blocks:                                        │
│        ├─ Validate tool name vs ACL (defense in depth)                       │
│        ├─ Dispatch to agent.execute_tool(name, input)                        │
│        ├─ Run guardrails (agent/guardrails.py)                               │
│        ├─ Append tool_result to messages                                     │
│        └─ Loop (max iterations capped)                                       │
│   5. Persist:                                                                │
│        ├─ AgentDecision row (rationale, tools used, output, correlation_id)  │
│        ├─ AgentMemory row (rolling context for next turn)                    │
│        └─ DomainEvent row (event sourcing — never mutate without an event)   │
│   6. Publish:                                                                │
│        └─ Redis pub/sub → WebSocket → React                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

Everything is **async**. All four agents are constructed once by the
orchestrator with a shared `anthropic.AsyncAnthropic` client and a shared
service bundle (db, event_store, maps, market_data) injected via
`agent.set_services(**services)`.

---

## 2. The Four Roles

Defined in `agent/tool_acl.py::AgentRole`. Each role has its own class in
`agent/{role}_agent.py`. All extend `BaseAgent` and must implement
`system_prompt()` and `tools()`.

| Role | Class | Tools (subset of `agent/tools/`) | Used for |
|------|-------|----------------------------------|----------|
| `buyer` | `BuyerAgent` | search, neighborhood, place_offer, accept_offer, counter, comps, intelligence | Searching listings, making/countering offers, reading market intel |
| `seller` | `SellerAgent` | list_property, evaluate_offer, set_asking_price, accept/counter, intelligence | Listing, pricing, responding to offers |
| `broker` | `BrokerAgent` | mediate_negotiation, market_analysis, generate_contract, schedule_inspection, comps, neighborhood, intelligence | ZOPA mediation, contracts, inspections |
| `assistant` | `AssistantAgent` | search, neighborhood, place_offer, counter, comps, intelligence | Generic helper / chat |

> **Adding a role** = (1) extend `AgentRole`, (2) add the class with prompt +
> tools, (3) register it in `TOOL_PERMISSIONS`, (4) register in
> `AgentOrchestrator.__init__.self.agents`. No other surface changes needed.

---

## 3. Tool Pipeline

Tools live under `agent/tools/` and are registered with `ToolRegistry`
(`agent/tool_registry.py`). They're the only way an agent can read from or
write to the system — there is no other side-effect surface.

```
agent.execute_tool(name, input)
        │
        ▼
ToolRegistry.dispatch(name, input, services)
        │
        ▼
agent/tools/{handler}.py::handle()    # search.py, offers.py, comps.py, ...
        │
        ▼
services.* (db, event_store, maps, market_data)
        │
        ▼
returns dict — appended to Claude message thread as tool_result
```

**Tool ACL** is enforced **twice**: once when filtering tool definitions sent
to Claude (`filter_tools_for_role`), and again when dispatching the tool call
(`validate_tool_access`). The permission map is a `MappingProxyType` and
cannot be mutated at runtime.

**Adding a tool** = (1) write `agent/tools/<name>.py` with a `handle(input,
services) -> dict`, (2) register in `ToolRegistry`, (3) add the tool name to
the relevant roles in `TOOL_PERMISSIONS`. The tool definition (name +
description + JSON schema) goes in the role's `tools()` method.

---

## 4. Guardrails

`agent/guardrails.py` holds hard-coded business rules that fire **before**
any tool side-effect lands. They are not negotiable per-request.

Key invariants:
- Offers must be ≥ 50% of asking price.
- Max auto-approved deal value: **$2M**. Above that, broker escalation is
  required.
- Counter-offers must respect the negotiation state machine (no `place_offer`
  while in `INSPECTION`).
- Jurisdiction-specific overrides live in `agent/guardrails_jp.py` (JP) and
  are dispatched via `agent/guardrails_dispatch.py`.

Guardrail violations return a structured `{error: ...}` dict to the agent,
which Claude is prompted to surface to the user as an explanation rather than
silently retry.

---

## 5. Negotiation Engine

`agent/negotiation_engine.py` is the multi-turn coordination loop that an
orchestrator invokes when both buyer and seller agents are participating.

State machine (`agent/negotiation.py`):

```
IDLE → OFFER_PENDING → COUNTER_PENDING → ... → ACCEPTED ─┐
                                                          ├─► CONTRACT_PHASE → INSPECTION → CLOSING → CLOSED
                            REJECTED / WITHDRAWN / ESCALATED
```

Built-in rules:
- **Round ≥ 5 with spread ≤ 3%** → suggest midpoint (ZOPA detection).
- **Round ≥ 5 with spread > 10%** → auto-attach broker mediation.
- **Round ≥ 10** → auto-escalate.
- **Deadlines:** 48h per offer, 72h for contract acceptance, 10 days
  inspection, 30 days closing. Timeouts emit
  `negotiation.deadline_breached` events.

The engine never holds in-memory state across requests — every transition is
written to `domain_events` with a correlation ID; the read model is rebuilt
from those events.

---

## 6. Memory & Decision Logging

Two tables, two purposes:

| Table | Purpose | Lifetime |
|-------|---------|----------|
| `agent_memory` | Rolling context an agent loads at the start of each turn (last N events, prior decisions, user prefs) | Per `(user_id, role)`, capped |
| `agent_decisions` | Full audit trail of every agent reasoning step — system prompt, tool calls made, raw output, correlation ID | Append-only |

Decisions are written **after** Claude returns and tools complete. The
`correlation_id` threads through middleware, agent, tool handlers, event
store, and pub/sub so a single user action can be reconstructed end-to-end.

---

## 7. The `/negotiate` Frontend Surface

The page at `frontend/src/pages/NegotiationPage.tsx` is **not just a
negotiation chat**. It composes three workspaces in one route:

1. **Session machinery** — Session Setup, Session State, Typed Actions, Offer
   History, Event Replay, Live WebSocket Feed. Backed by `/api/negotiations/*`.
2. **Social Interaction Simulation (Persona Risk Workspace)** — pick a
   trigger user, zip, income band, and topics; watch round-by-round
   household stance and sentiment shifts. Backed by `/api/social-sim/*`. This
   is the surface used for **"how would different personas move under a
   given pressure"** risk assessment.
3. **Agent Sidecar** — direct Claude-API agent chat scoped to the session
   correlation ID.

See `SOCIAL_SIMULATION_IMPLEMENTATION.md` for the underlying simulator
contract and `doc/SOCIAL_SIMULATION_IMPLEMENTATION.md` for the layered runtime
that's gradually replacing the legacy loop.

---

## 8. Layered Domain Runtime Boundary

The agent runtime is **stateful** (DB writes, Claude calls, WebSocket
broadcasts). The layered runtime under `domain/` is **stateless**
(side-effect-free projections). They meet at two seams:

- **Read seam:** `services/market_state.build_snapshot(db, property_id)`
  pulls signal rows and returns a frozen `MarketContextSnapshot` that any
  agent or decision policy can consume.
- **Write seam:** future work — wire `DecisionRuntime` (see
  `domain/decisions/`) into `AgentOrchestrator.route_message` so each agent
  turn surfaces a structured `DecisionRecommendation` alongside the raw
  Claude tool output. Not yet implemented.

Until that wiring lands, the layered runtime is opt-in: it ships with full
test coverage but no live consumers in the agent path.

---

## 9. Operational Notes

- **Async-first.** Every DB / Redis / HTTP / Claude call is `await`-ed. Use
  `asyncio.Semaphore` for fan-out concurrency (see
  `services/batch_simulator.py` for the canonical pattern).
- **Provider Protocol.** External integrations (Claude, TomTom, MiroFish,
  market data) use the same `Mock + Real` Protocol pattern. Tests inject
  Mock; live runs select via `*_MODE` / `*_PROVIDER` env vars.
- **Circuit breaker.** External HTTP (`intelligence/`, `services/maps.py`)
  retries 3× with exponential backoff and opens the circuit after 5
  consecutive failures.
- **No bypass paths.** There is exactly one way for an agent to act on the
  world: ACL-validated tool dispatch through `BaseAgent.execute_tool`.
  Anything else is a bug.
