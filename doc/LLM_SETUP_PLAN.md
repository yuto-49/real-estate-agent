# Phase 1: LLM Provider Setup & Usability Plan

## Current State Analysis

The platform makes LLM calls from **5 distinct call sites**, each with different requirements:

| Call Site | File | Current Model | Calls/Session | Latency | Reasoning |
|---|---|---|---|---|---|
| Agent conversations (buyer/seller/broker/assistant) | `agent/base_agent.py:23` | `claude-sonnet-4-6` | ~10 tool rounds × N negotiations | Real-time | High (multi-step tool use) |
| Negotiation simulation | `services/negotiation_simulator.py:79` | `claude-sonnet-4-6` (via BuyerAgent/SellerAgent) | 10-30 rounds × 3 agents | Async batch | Medium |
| Batch simulation | `services/batch_simulator.py` | Same as above (creates NegotiationSimulator instances) | 6 scenarios × 30 rounds | Background | Medium |
| Social simulation | `services/social_simulator.py:463` | `claude-haiku-4-5-20251001` | Hundreds per run | Background | Low (JSON output) |
| Persona generation | `services/persona_generator.py:128` | `claude-sonnet-4-20250514` | ~2 per simulation | One-shot | Low |

### Current Monthly LLM Cost Estimate (All Claude)

Assuming 100 active users/day, ~5 negotiations/day, 2 simulations/day:

| Call Site | Est. Tokens/Month (Input) | Est. Tokens/Month (Output) | Cost/Month |
|---|---|---|---|
| Agent conversations | ~15M | ~5M | ~$120 |
| Negotiation sim | ~40M | ~15M | ~$345 |
| Batch sim | ~80M | ~30M | ~$690 |
| Social sim | ~20M | ~5M | ~$23 (Haiku) |
| Persona gen | ~2M | ~1M | ~$21 |
| **Total** | | | **~$1,200/mo** |

---

## Recommended LLM Strategy: Gemini Flash 2.0 as Primary

After analyzing the codebase, **Google Gemini Flash 2.0 is the best single provider** for this platform. Here's why:

### Why Gemini Flash 2.0 Wins

| Factor | Gemini Flash 2.0 | DeepSeek-V3 | Groq Llama 3.3 | Claude Sonnet |
|---|---|---|---|---|
| **Price (input/output per 1M)** | $0.10 / $0.40 | $0.27 / $1.10 | $0.59 / $0.79 | $3.00 / $15.00 |
| **Tool use support** | Native | OpenAI-compatible | OpenAI-compatible | Native |
| **Data residency** | US/EU (Google Cloud) | China | US (Groq) | US (Anthropic) |
| **Rate limits (free tier)** | 1,500 RPM | 500 RPM | 30 RPM | 50 RPM |
| **Context window** | 1M tokens | 64K | 128K | 200K |
| **Structured output (JSON)** | Native `response_mime_type` | Via prompt | Via prompt | Via tool_use |
| **Speed** | ~150 tok/s | ~60 tok/s | ~900 tok/s | ~80 tok/s |

**Gemini Flash 2.0** is the sweet spot:
- **30x cheaper** than Claude Sonnet on input tokens
- **37x cheaper** on output tokens
- No data residency concerns (US-based Google infrastructure)
- Native tool/function calling (critical — all 4 agents use tools heavily)
- 1M context window handles the large negotiation contexts with intelligence reports
- Google's free tier (1,500 RPM) is generous enough for MVP without paying anything

### Recommended Routing

```
┌─────────────────────────────┬──────────────────────┬───────────────┐
│ Call Site                    │ Model                │ Why           │
├─────────────────────────────┼──────────────────────┼───────────────┤
│ BrokerAgent (contracts,     │ Gemini Flash 2.0     │ Tool use +    │
│ compliance, mediation)      │                      │ reasoning     │
├─────────────────────────────┼──────────────────────┼───────────────┤
│ BuyerAgent / SellerAgent    │ Gemini Flash 2.0     │ Real-time     │
│ (live negotiation)          │                      │ tool use      │
├─────────────────────────────┼──────────────────────┼───────────────┤
│ AssistantAgent (investment  │ Gemini Flash 2.0     │ Tool use +    │
│ analysis chat)              │                      │ large context │
├─────────────────────────────┼──────────────────────┼───────────────┤
│ NegotiationSimulator        │ Gemini Flash-Lite    │ Batch, high   │
│ (automated rounds)          │ ($0.075/$0.30)       │ volume        │
├─────────────────────────────┼──────────────────────┼───────────────┤
│ BatchSimulator              │ Gemini Flash-Lite    │ 6× parallel   │
│ (scenario variants)         │                      │ scenarios     │
├─────────────────────────────┼──────────────────────┼───────────────┤
│ SocialSimulator             │ Gemini Flash-Lite    │ Hundreds of   │
│ (opinion rounds)            │                      │ short calls   │
├─────────────────────────────┼──────────────────────┼───────────────┤
│ PersonaGenerator            │ Gemini Flash-Lite    │ One-shot JSON │
├─────────────────────────────┼──────────────────────┼───────────────┤
│ Fallback (if Gemini down)   │ Claude Sonnet 4.6    │ Existing code │
│                             │                      │ already works │
└─────────────────────────────┴──────────────────────┴───────────────┘
```

### Projected Cost After Migration

| Call Site | Model | Cost/Month |
|---|---|---|
| Agent conversations | Gemini Flash 2.0 | ~$3.50 |
| Negotiation sim | Gemini Flash-Lite | ~$5.50 |
| Batch sim | Gemini Flash-Lite | ~$11 |
| Social sim | Gemini Flash-Lite | ~$2 |
| Persona gen | Gemini Flash-Lite | ~$0.40 |
| **Total** | | **~$22/mo** |

**Savings: ~$1,178/mo (98% reduction)**

---

## Implementation Plan

### Step 1: LLM Provider Protocol (`services/llm_provider.py`)

Define a provider-agnostic interface that all agents use:

```python
from typing import Protocol, Any
from dataclasses import dataclass

@dataclass(frozen=True)
class LLMResponse:
    text: str
    tool_calls: list[dict[str, Any]]
    stop_reason: str  # "end_turn" | "tool_use"
    input_tokens: int
    output_tokens: int

class LLMProvider(Protocol):
    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse: ...
```

### Step 2: Concrete Providers

**GeminiProvider** (primary):
```python
class GeminiProvider:
    """Google Gemini via the OpenAI-compatible endpoint."""

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

    async def complete(self, *, model, system, messages, tools, max_tokens) -> LLMResponse:
        # Convert Anthropic tool schema → OpenAI function schema
        # Call self.client.chat.completions.create(...)
        # Normalize response → LLMResponse
        ...
```

**AnthropicProvider** (fallback):
```python
class AnthropicProvider:
    """Existing Anthropic Claude — used as fallback."""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)

    async def complete(self, *, model, system, messages, tools, max_tokens) -> LLMResponse:
        # Existing logic from base_agent.py process_message
        # Normalize response → LLMResponse
        ...
```

### Step 3: LLM Router (`services/llm_router.py`)

```python
from agent.tool_acl import AgentRole

# Model assignments per use case
AGENT_MODELS: dict[AgentRole, tuple[str, str]] = {
    # (provider_key, model_name)
    AgentRole.BROKER:    ("gemini", "gemini-2.0-flash"),
    AgentRole.BUYER:     ("gemini", "gemini-2.0-flash"),
    AgentRole.SELLER:    ("gemini", "gemini-2.0-flash"),
    AgentRole.ASSISTANT: ("gemini", "gemini-2.0-flash"),
}

SIMULATION_MODEL = ("gemini", "gemini-2.0-flash-lite")
SOCIAL_SIM_MODEL = ("gemini", "gemini-2.0-flash-lite")
PERSONA_MODEL    = ("gemini", "gemini-2.0-flash-lite")
FALLBACK_MODEL   = ("anthropic", "claude-sonnet-4-6")

class LLMRouter:
    def __init__(self, providers: dict[str, LLMProvider]):
        self.providers = providers

    def get_provider(self, use_case: str) -> tuple[LLMProvider, str]:
        """Returns (provider, model_name) for a given use case."""
        ...

    def get_agent_provider(self, role: AgentRole) -> tuple[LLMProvider, str]:
        """Returns (provider, model_name) for an agent role."""
        provider_key, model = AGENT_MODELS.get(role, FALLBACK_MODEL)
        return self.providers[provider_key], model
```

### Step 4: Refactor BaseAgent

Change `BaseAgent` to accept an `LLMProvider` + model name instead of `anthropic.AsyncAnthropic`:

```python
class BaseAgent(ABC):
    def __init__(self, provider: LLMProvider, model: str, role: AgentRole | None = None):
        self.provider = provider
        self.model = model
        self.role = role
        ...

    async def process_message(self, message, context, conversation_history):
        # Replace self.client.messages.create() with:
        response = await self.provider.complete(
            model=self.model,
            system=system,
            messages=messages,
            tools=self.filtered_tools(),
            max_tokens=self.max_tokens,
        )
        ...
```

### Step 5: Refactor Orchestrator

```python
class AgentOrchestrator:
    def __init__(self, db, event_bus, router: LLMRouter, ...):
        self.router = router
        self.agents = {}
        for role_name, role_enum in [("buyer", AgentRole.BUYER), ...]:
            provider, model = router.get_agent_provider(role_enum)
            self.agents[role_name] = AgentClass(provider, model)
```

### Step 6: Refactor Simulators

- `NegotiationSimulator.__init__`: use `router.get_provider("simulation")` instead of `anthropic.AsyncAnthropic`
- `social_simulator.py`: use `router.get_provider("social_sim")`
- `persona_generator.py`: use `router.get_provider("persona")`

### Step 7: Config Updates

```python
# config.py additions
google_api_key: str = ""          # Gemini
llm_provider: str = "gemini"      # "gemini" | "anthropic" (global default)
simulation_llm_provider: str = "gemini"  # override for simulations
```

### Step 8: Tool Schema Translation

Anthropic and OpenAI/Gemini use different tool schemas. Build a translator:

```python
def anthropic_to_openai_tools(tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool format to OpenAI function calling format.

    Anthropic: {"name": ..., "description": ..., "input_schema": {...}}
    OpenAI:    {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]
```

---

## Usability Improvements

Beyond cost, the LLM abstraction enables concrete usability improvements:

### 1. Response Speed (User-Visible)

**Current:** Claude Sonnet ~80 tok/s → typical agent response takes 3-5 seconds.
**With Gemini Flash:** ~150 tok/s → responses in 1.5-3 seconds.
**For simulations (Groq fallback):** ~900 tok/s → 10-round negotiation completes in seconds instead of minutes.

Users will immediately feel the difference in chat responsiveness.

### 2. Streaming Responses

The current `process_message` loop waits for complete responses. With the provider abstraction, add streaming:

```python
class LLMProvider(Protocol):
    async def complete(...) -> LLMResponse: ...
    async def stream(...) -> AsyncIterator[LLMChunk]: ...
```

This enables **token-by-token streaming** over the existing WebSocket connection (`/ws/negotiation/{id}`), so users see the agent "typing" in real-time instead of waiting for a complete response.

### 3. Cost Tracking Dashboard

Add token counting to every LLM call via `LLMResponse.input_tokens` / `output_tokens`:

- Store per-request cost in `domain_events` table (already exists, add `llm_cost_usd` to payload)
- New API endpoint: `GET /api/admin/llm-costs` — aggregate by agent role, time period
- Frontend widget on DashboardPage showing daily/monthly LLM spend
- Alerts when spend exceeds configurable threshold

### 4. Simulation Speed

The biggest usability pain point is **simulation wait time**. Currently:
- 1 negotiation sim (10 rounds) = ~30 Claude API calls = ~2-3 minutes
- Batch sim (6 scenarios × 10 rounds) = ~180 calls = ~15-20 minutes

With Gemini Flash-Lite:
- Same negotiation sim = ~45 seconds (faster inference + cheaper = can parallelize more)
- Batch sim with increased concurrency = ~2-3 minutes

This makes simulations usable as an interactive tool rather than a background job.

### 5. Graceful Fallback Chain

If Gemini is down, automatically fall back to Claude (existing code already works):

```
Gemini Flash 2.0 → (timeout/error) → Claude Sonnet 4.6
```

The circuit breaker pattern already exists in `intelligence/mirofish_client.py` — reuse the same tenacity retry + circuit breaker for LLM calls.

### 6. Model Quality A/B Testing

The router makes it trivial to run experiments:
- Route 10% of BuyerAgent calls to Claude, 90% to Gemini
- Compare negotiation outcomes (final price, rounds to close)
- Data-driven model selection rather than assumptions

---

## File Changes Summary

| File | Change |
|---|---|
| `services/llm_provider.py` | **NEW** — LLMProvider protocol, LLMResponse dataclass |
| `services/llm_providers/gemini.py` | **NEW** — GeminiProvider implementation |
| `services/llm_providers/anthropic.py` | **NEW** — AnthropicProvider implementation |
| `services/llm_router.py` | **NEW** — LLMRouter, model routing table |
| `services/llm_providers/tool_schema.py` | **NEW** — Anthropic ↔ OpenAI tool schema translator |
| `agent/base_agent.py` | **MODIFY** — Accept LLMProvider instead of anthropic client |
| `agent/orchestrator.py` | **MODIFY** — Use LLMRouter to create agents |
| `agent/buyer_agent.py` | **MODIFY** — Pass provider+model to super().__init__ |
| `agent/seller_agent.py` | **MODIFY** — Same |
| `agent/broker_agent.py` | **MODIFY** — Same |
| `agent/assistant_agent.py` | **MODIFY** — Same |
| `services/negotiation_simulator.py` | **MODIFY** — Use router for agent creation |
| `services/social_simulator.py` | **MODIFY** — Use provider instead of anthropic client |
| `services/persona_generator.py` | **MODIFY** — Use provider instead of anthropic client |
| `config.py` | **MODIFY** — Add google_api_key, llm_provider settings |
| `pyproject.toml` | **MODIFY** — Add `openai` SDK dependency (for Gemini OpenAI-compat) |
| `tests/test_llm_provider.py` | **NEW** — Unit tests for provider abstraction |
| `tests/test_llm_router.py` | **NEW** — Unit tests for routing logic |

---

## Migration Path

1. **Week 1, Days 1-2:** Build provider abstraction + Gemini provider + tool schema translator
2. **Week 1, Days 3-4:** Refactor BaseAgent + Orchestrator + all 4 agent classes
3. **Week 1, Day 5:** Refactor simulators (negotiation, batch, social, persona)
4. **Week 2, Day 1:** Integration tests — run existing test suite against Gemini provider
5. **Week 2, Day 2:** Add fallback chain + circuit breaker for LLM calls
6. **Week 2, Day 3:** Deploy with `llm_provider=gemini` in staging, `anthropic` still default in prod
7. **Week 2, Day 4-5:** Validate quality, flip prod to Gemini, monitor costs

### Rollback Plan

Set `LLM_PROVIDER=anthropic` in environment → all traffic routes to Claude instantly. No code change needed.

---

## Why NOT DeepSeek or Groq as Primary?

**DeepSeek:**
- China-based — data residency risk for a US real estate platform handling PII (addresses, financial data, user profiles)
- Tool calling is OpenAI-compatible but less mature than Gemini's native function calling
- Lower rate limits on free tier (500 RPM vs Gemini's 1,500 RPM)
- Good as a secondary option for reasoning-heavy tasks if residency is acceptable

**Groq:**
- Fastest inference (~900 tok/s) but limited model selection (only open-source models)
- 30 RPM free tier is too restrictive for production
- Llama 3.3 70B tool calling is less reliable than Gemini or Claude
- Best as a speed-optimized option for batch simulations only, not as primary

**Claude Sonnet:**
- Best quality, but 30x more expensive than Gemini Flash
- Keep as fallback for when quality matters most or Gemini is unavailable
- The existing codebase already works with Claude — zero migration risk as fallback
