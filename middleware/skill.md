# middleware/ — HTTP Middleware

## Purpose
FastAPI middleware for request authentication, correlation ID injection, and rate limiting.

## Key Files

| File | Role |
|------|------|
| `auth.py` | Supabase JWT verification — RS256 via JWKS with HS256 fallback; development passthrough when unconfigured |
| `correlation.py` | Injects UUID correlation ID into every request for distributed tracing |
| `rate_limit.py` | Rate limiting middleware for API endpoints |

## Patterns
- **Auth passthrough:** When `SUPABASE_JWT_ISSUER`/`SUPABASE_JWKS_URL` are empty, auth is disabled — useful for tests and local dev
- **Correlation threading:** UUID propagated through logs, events, and agent decisions
- **FastAPI dependencies:** Exposed as `Depends()` for route-level injection

## Testing
- Tests in `tests/test_auth_middleware.py`, `tests/test_correlation_id.py`
