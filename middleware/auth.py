"""Supabase JWT authentication middleware.

Verifies bearer tokens issued by Supabase Auth. Supports two modes:

- **JWKS (RS256/ES256)** — modern Supabase projects. Verifies via the
  project's published JSON Web Key Set, fetched once and cached in-process.
- **HS256 (legacy symmetric)** — fall-back for older projects that haven't
  rotated to asymmetric keys. Set ``SUPABASE_JWT_SECRET`` to enable.

In ``ENVIRONMENT=development`` requests without an Authorization header are
allowed through (returning ``None``) so local UIs and tests don't need a
token. Production rejects unauthenticated requests with 401.
"""

from __future__ import annotations

import logging
from typing import Any

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

# Module-level cache so we don't re-download the JWKS on every request.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient | None:
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client
    if not settings.supabase_jwks_url:
        return None
    _jwks_client = PyJWKClient(
        settings.supabase_jwks_url,
        cache_keys=True,
        lifespan=3600,
    )
    return _jwks_client


def _reset_jwks_cache() -> None:
    """Test helper — clears the cached JWKS client between unit tests."""
    global _jwks_client
    _jwks_client = None


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase-issued JWT and return its decoded payload.

    Raises :class:`fastapi.HTTPException` (401) on any verification failure.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    issuer = settings.supabase_jwt_issuer or None
    audience = settings.supabase_jwt_audience or None
    decode_kwargs: dict[str, Any] = {}
    if audience:
        decode_kwargs["audience"] = audience
    if issuer:
        decode_kwargs["issuer"] = issuer

    jwks_client = _get_jwks_client()

    try:
        if jwks_client is not None:
            signing_key = jwks_client.get_signing_key_from_jwt(token).key
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256", "ES256"],
                **decode_kwargs,
            )
        elif settings.supabase_jwt_secret:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                **decode_kwargs,
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Supabase auth is not configured. Set SUPABASE_JWKS_URL "
                    "(modern projects) or SUPABASE_JWT_SECRET (legacy)."
                ),
            )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidIssuerError as exc:
        raise HTTPException(status_code=401, detail="Invalid token issuer") from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(status_code=401, detail="Invalid token audience") from exc
    except jwt.InvalidTokenError as exc:
        logger.info("JWT verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    return payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> dict[str, Any] | None:
    """FastAPI dependency. Returns the decoded JWT payload or ``None`` in dev.

    The payload's ``sub`` claim is the Supabase user UUID — match it against
    ``UserProfile.supabase_user_id`` to locate the local profile row.
    """
    if not credentials:
        if settings.environment == "development":
            return None
        raise HTTPException(status_code=401, detail="Authentication required")

    return verify_supabase_jwt(credentials.credentials)


async def require_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> dict[str, Any]:
    """Stricter variant of :func:`get_current_user` — always 401 if missing."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    return verify_supabase_jwt(credentials.credentials)
