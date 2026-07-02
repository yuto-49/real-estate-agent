# agent/ — Multi-Agent Persona Council

## Purpose
Orchestrates parallel Claude API calls across analyst personas (buyer, seller, broker, investor) to produce listing analysis verdicts and aggregated scores.

## Key Files

| File | Role |
|------|------|
| `analyst_council.py` | `review_listing()` — dispatches 4 parallel Claude Haiku calls, aggregates into `ListingAnalysis` (score 0-100, summary) |
| `analyst_personas.py` | `COUNCIL` tuple — persona definitions with system prompts for each analyst perspective |

## Subdirectories

| Path | Role |
|------|------|
| `tools/` | Tool handlers for agent actions: search, neighborhood, offers, listings, comps, counter, broker, intelligence |

## Key Types
- `AnalystVerdict` — single persona's score + reasoning
- `ListingAnalysis` — aggregated verdict with composite score and summary

## Patterns
- **Parallel execution:** All persona calls run concurrently via `asyncio.gather`
- **Tool ACL:** Agent tools gated by frozen permission map in `tool_acl.py` — never bypass
- **Prompt versioning:** Prompts are versioned (v2.0.0) for reproducibility

## Dependencies
- `anthropic` (Claude API)
- `db/models.py` (Property model for listing data)
- `services/` (market data, event store)

## Testing
- Tests in `tests/test_analyst_council.py`
- Mock Claude API responses — no live API calls in tests
