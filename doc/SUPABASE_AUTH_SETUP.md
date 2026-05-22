# Supabase Auth Setup

This document explains the authentication wiring added in the May 9 patch:
how the JWT verification works, what env vars to set, how the dev account is
provisioned, and how the frontend signs users in. Read top-to-bottom on first
setup; later you can jump to a specific section.

---

## 1. What was wrong before

The previous `middleware/auth.py` was a **placeholder**:

- It signed homemade tokens with `hmac` using the **Anthropic API key as the
  signing secret**. That's a bad pattern: a vendor key was doing double duty
  as a session-signing key, and the same value was sent to Anthropic on every
  agent call.
- It never read `SUPABASE_JWT_ISSUER` or `SUPABASE_JWKS_URL` even though those
  vars exist in `config.py`.
- It bypassed auth entirely when `ENVIRONMENT=development` (still does, but
  now that's an explicit, documented choice).

---

## 2. What changed

### Backend
| File | What it does now |
|---|---|
| `config.py` | Added `supabase_jwt_audience` (default `authenticated`), `supabase_jwt_secret` (HS256 fallback), `supabase_service_role_key` (admin-only, used by one script). |
| `middleware/auth.py` | Real JWT verifier. Uses `PyJWKClient` to fetch the project's JWKS once and cache it. Falls back to HS256 when `SUPABASE_JWT_SECRET` is set instead of the JWKS URL. Maps Supabase errors → HTTP 401. |
| `tests/test_auth_middleware.py` | 13 tests covering valid token, expired, wrong issuer, wrong audience, bad signature, garbage input, dev-mode bypass, prod enforcement, and the strict `require_current_user` variant. |
| `scripts/create_dev_user.py` | Creates a Supabase user via the admin API + a matching `UserProfile` row, or backfills `supabase_user_id` on existing rows by email. |
| `.env.example` | New Supabase Auth section with all vars and a pointer to this doc. |

### Frontend
| File | What it does |
|---|---|
| `src/utils/supabase.ts` | Exports a singleton `supabase` client built from `VITE_SUPABASE_URL` + `VITE_SUPABASE_PUBLISHABLE_KEY`. |
| `src/hooks/useAuth.ts` | Tiny wrapper around `supabase.auth` returning `{ session, user, loading, signIn, signUp, signOut }`. |
| `src/utils/api.ts` | Every `fetchJSON` / `fetchRootJSON` call now attaches `Authorization: Bearer <access_token>` automatically when a session exists. |
| `src/pages/SignInPage.tsx` | Email + password form with toggle between sign-in and sign-up, plus a "Fill dev credentials" shortcut. |
| `src/App.tsx` | Adds `/signin` route, an `AuthStatus` chip in the header (email + sign-out), and a `<RequireAuth>` wrapper protecting `/negotiate/*` and `/profile/*`. Public routes (Dashboard, Analysis, Simulation) stay open. |
| `src/vite-env.d.ts` | Declares the four `VITE_*` envs so TypeScript knows about them. |

### Database
- The Phase B / `f3a8b1d472e0` migrations already added `user_profiles.supabase_user_id` (unique, indexed). The auth flow uses this column to link a Supabase user (`sub` claim) to a local `UserProfile` row.

---

## 3. The two verification modes

Modern Supabase projects (created or rotated since 2024) sign JWTs with
**RS256** and publish a **JWKS** — JSON Web Key Set — at a stable URL. We
verify against the public key fetched from that URL. This is the default.

Older projects use a **shared HMAC secret (HS256)**. If your project is in
this mode, set `SUPABASE_JWT_SECRET` and leave `SUPABASE_JWKS_URL` empty —
the middleware will detect the absence of a JWKS URL and fall back to HS256.

| Project type | Set | Skip |
|---|---|---|
| Modern (JWKS) | `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` | `SUPABASE_JWT_SECRET` |
| Legacy (HS256) | `SUPABASE_JWT_SECRET`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` | `SUPABASE_JWKS_URL` |

Quick check which mode you're in:

```bash
curl -s "${SUPABASE_URL}/auth/v1/.well-known/jwks.json" | head
```

- Returns `{"keys":[{"kty":"RSA",...}]}` → **JWKS mode** (use the modern row).
- Returns `{"keys":[]}` → **HS256 mode** (use the legacy row, grab the JWT secret from the dashboard).

---

## 4. Required env vars

Copy this into `.env` (replace `YOUR-PROJECT` with your project ref):

```env
# Backend Auth
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_JWT_ISSUER=https://YOUR-PROJECT.supabase.co/auth/v1
SUPABASE_JWKS_URL=https://YOUR-PROJECT.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_JWT_AUDIENCE=authenticated

# Optional / mode-specific
# SUPABASE_JWT_SECRET=        # only if your project is HS256
# SUPABASE_SERVICE_ROLE_KEY=  # admin key — needed ONLY by scripts/create_dev_user.py

# Frontend (publishable / anon key — safe to ship in JS bundle)
VITE_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_xxxxxxxxxxxxxxxx
```

Where to find each value in the Supabase dashboard
(`https://supabase.com/dashboard/project/<ref>`):

| Var | Path in dashboard |
|---|---|
| `SUPABASE_URL` / `VITE_SUPABASE_URL` | Settings → API → Project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Settings → API → Project API Keys → `anon` / `publishable` |
| `SUPABASE_SERVICE_ROLE_KEY` | Settings → API → Project API Keys → `service_role` (sensitive) |
| `SUPABASE_JWT_SECRET` (HS256 only) | Settings → API → JWT Settings → JWT Secret |
| `SUPABASE_JWT_ISSUER` | `<SUPABASE_URL>/auth/v1` (constant pattern) |
| `SUPABASE_JWKS_URL` | `<SUPABASE_URL>/auth/v1/.well-known/jwks.json` (constant pattern) |

---

## 5. Creating the dev account

Once `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set:

```bash
python scripts/create_dev_user.py
```

Default credentials:
```
Email:    dev@realestate.local
Password: DevPassword123!
```

Override either:
```bash
python scripts/create_dev_user.py --email me@example.com --password 'AnotherPw!'
```

The script:
1. Looks up `dev@realestate.local` in Supabase Auth via the admin API.
2. Creates the Supabase user with `email_confirm=True` if missing (no
   confirmation mail sent — the account is immediately usable).
3. Either creates a fresh `UserProfile` row or links an existing one by
   email, populating `UserProfile.supabase_user_id` with the Supabase
   user UUID.

### Backfilling existing UserProfiles

If you already have local `UserProfile` rows that should map to existing
Supabase users:

```bash
python scripts/create_dev_user.py --backfill
```

Walks every local `UserProfile` row, finds a Supabase user with the same
email, and writes the `sub` UUID into `supabase_user_id`. Idempotent.

---

## 6. How a request actually flows

```
  Browser                                Backend
  ───────                                ───────
  1. SignInPage submits {email, password}
       ↓ supabase.auth.signInWithPassword
  2. Supabase returns { session.access_token }
       ↓ stored in localStorage (key: real-estate-agent.session)
  3. Any api.* call:
       getAccessToken() reads session
       fetch(url, headers: { Authorization: 'Bearer <token>' })
                                          ↓
                                     middleware/auth.get_current_user
                                          ↓
                                     verify_supabase_jwt:
                                       - fetch JWKS (cached 1h)
                                       - jwt.decode(token, key, RS256,
                                                    issuer=..., audience=...)
                                       - return payload {sub, email, ...}
                                          ↓
                                     route handler reads user via Depends
```

The signing-key fetch happens **once per process per hour** (cache lifespan
of `PyJWKClient`), so there's no per-request HTTP overhead after warm-up.

---

## 7. Linking the JWT `sub` to a local user

The Supabase JWT carries `sub` = the Supabase user UUID. To find the local
profile row:

```python
from sqlalchemy import select
from db.models import UserProfile

async def resolve_user(db, jwt_payload):
    sub = jwt_payload["sub"]
    return (await db.execute(
        select(UserProfile).where(UserProfile.supabase_user_id == sub)
    )).scalar_one_or_none()
```

Use this inside route handlers that previously took `user_id` from the URL:

```python
from middleware.auth import require_current_user

@router.get("/me/negotiations")
async def my_negotiations(
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(require_current_user),
):
    user = await resolve_user(db, payload)
    ...
```

---

## 8. Dev vs. prod enforcement

`get_current_user` returns `None` when:
- there's no `Authorization` header AND
- `ENVIRONMENT=development`.

This keeps local development friction-free. Two ways to lock it down:

1. **Per-route** — switch the dependency on sensitive routes from
   `get_current_user` to `require_current_user` (raises 401 in any environment
   when no token is present).
2. **Globally** — set `ENVIRONMENT=production` in `.env`. Every protected
   route then enforces the token.

The frontend's `<RequireAuth>` wrapper currently protects `/negotiate/*` and
`/profile/*` regardless of backend mode. Add it to more routes to gate the UI
even when the backend is permissive.

---

## 9. Things to clean up after migration

- Delete the legacy `create_token` / `decode_token` from any handler that
  still imports them (the new `middleware/auth.py` no longer exports those).
- Rotate the Anthropic API key — the previous middleware used it as an
  HMAC secret, so it leaked into any signed token observable in logs.
- Once the JWKS verifier proves stable, flip `ENVIRONMENT=production` so
  unauthenticated requests are rejected by default.

---

## 10. Test coverage

`tests/test_auth_middleware.py` exercises the verifier directly via PyJWT
HS256 mode (no Supabase server needed):

| Test | What it asserts |
|---|---|
| `valid_token_returns_payload` | Happy path: payload claims preserved |
| `expired_token_raises_401` | `exp` enforcement |
| `wrong_issuer_raises_401` | Catches token reuse from another project |
| `wrong_audience_raises_401` | Audience check active |
| `bad_signature_raises_401` | Signature verification active |
| `garbage_token_raises_401` | Malformed token handled |
| `empty_token_raises_401` | No silent pass-through on empty bearer |
| `without_config_raises_500` | Misconfigured env yields 500, not silent allow |
| `get_current_user_*` (3) | Header-driven dev/prod behavior |
| `require_current_user_*` (2) | Strict variant always demands a token |

Run with:
```bash
pytest tests/test_auth_middleware.py -v
```
