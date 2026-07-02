# tests/ — Test Suite

## Purpose
Comprehensive pytest test suite (~585 tests) using in-memory SQLite, fakeredis, and mocked external services. No Docker or live API calls required.

## Key Files

| File | Role |
|------|------|
| `conftest.py` | Shared fixtures — in-memory SQLite async engine, event loop scope, fakeredis, JSONB-to-JSON patching |
| `test_api_*.py` | Route/endpoint integration tests |
| `test_domain_*.py` | Pure-function unit tests for domain layers |
| `test_analyst_council.py` | Agent council tests with mocked Claude API |
| `test_stress_test.py` | Monte Carlo stress test verification |
| `test_depreciation_jp.py` | JP depreciation calculation tests |
| `test_auth_middleware.py` | Auth middleware tests |
| `test_correlation_id.py` | Correlation ID middleware tests |
| `test_signal_providers.py` | Market signal provider tests |
| `test_market_state.py` | Market state snapshot tests |

## Subdirectories

| Path | Role |
|------|------|
| `fixtures/` | Test data fixtures (JSON, CSV) |

## Commands
```bash
pytest tests/ -v                           # full suite
pytest tests/ --cov=. --cov-report=term-missing  # with coverage
pytest tests/test_signal_providers.py -v   # single file
```

## Patterns
- **In-memory SQLite** — no PostgreSQL needed for tests
- **fakeredis** — no Redis server needed
- **httpx.MockTransport** — mock all external HTTP calls
- **No live API calls** — Claude API, Supabase, and all providers are mocked
