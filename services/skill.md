# services/ — Business Logic & Integrations

## Purpose
Cross-cutting business logic layer bridging pure domain projections with database persistence, external APIs, and orchestration. ~24 modules covering portfolio analysis, market signals, event sourcing, and job queues.

## Key Files

| File | Role |
|------|------|
| `market_state.py` | `build_snapshot(db, property_id)` — async entry point producing `MarketContextSnapshot` from DB |
| `signal_writer.py` | `upsert_signal()` — idempotent per-calendar-day market signal writer |
| `portfolio_summary.py` | `build_portfolio_summary()` — aggregator for `/summary` endpoint |
| `strategy_runner.py` | `execute_strategy_run()` — in-process strategy simulation store |
| `holding_decision.py` | `compute_holding_decision()` — extracted decision logic for holdings |
| `event_store.py` | Domain event persistence |
| `market_data.py` | Provider delegation for market data |
| `tenant_pool.py` | Income-band-aware tenant queries over HouseholdProfile |
| `property_recommender.py` | Property recommendation engine |
| `unified_report.py` | `reconcile_unified_report()` — analysis vs simulation reconciliation |
| `strategy_profile.py` | `extract_strategy_profile()` — free-text to StrategyProfile (LLM-pluggable) |
| `address_jp.py` | Japanese address parsing |
| `money_jp.py` | JPY money formatting |
| `pubsub.py` | Redis pub/sub for real-time events |
| `redis.py` | Redis client wrapper |
| `metrics.py` | Application metrics |
| `logging.py` | Structured logging setup (structlog) |
| `job_queue.py` | Background job queue |

## Subdirectories

| Path | Role |
|------|------|
| `signal_providers/` | Pluggable market signal providers — Protocol + registry pattern |
| `providers_jp/` | Japan-specific data sources: REINS, e-Stat, Reinfolib |

## Patterns
- **Provider Protocol:** All external data sources implement `MarketSignalProvider` protocol
- **Signal writer:** All market signal writes go through `upsert_signal` — never `db.add(MarketSignal(...))` directly
- **Async-first:** All DB, Redis, and HTTP calls are async
- **Circuit breaker:** External calls use tenacity retry + circuit breaker
- **httpx injection:** External providers accept `httpx.AsyncClient` for testability
