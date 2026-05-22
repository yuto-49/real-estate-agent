"""Tests for the Supabase JWT verification middleware."""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from config import settings
from middleware import auth


HS_SECRET = "test-supabase-jwt-secret-please-rotate"
TEST_ISSUER = "https://example.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"


def _make_token(
    *,
    sub: str = "user-uuid-123",
    email: str = "dev@example.com",
    issuer: str = TEST_ISSUER,
    audience: str = TEST_AUDIENCE,
    expires_in: int = 3600,
    secret: str = HS_SECRET,
    algorithm: str = "HS256",
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + expires_in,
        "role": "authenticated",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture(autouse=True)
def _hs256_supabase_settings(monkeypatch):
    """Configure HS256 mode for tests so we don't need a real JWKS endpoint."""
    monkeypatch.setattr(settings, "supabase_jwt_secret", HS_SECRET)
    monkeypatch.setattr(settings, "supabase_jwks_url", "")
    monkeypatch.setattr(settings, "supabase_jwt_issuer", TEST_ISSUER)
    monkeypatch.setattr(settings, "supabase_jwt_audience", TEST_AUDIENCE)
    monkeypatch.setattr(settings, "environment", "production")
    auth._reset_jwks_cache()
    yield
    auth._reset_jwks_cache()


def test_verify_valid_token_returns_payload():
    token = _make_token()
    payload = auth.verify_supabase_jwt(token)
    assert payload["sub"] == "user-uuid-123"
    assert payload["email"] == "dev@example.com"
    assert payload["iss"] == TEST_ISSUER


def test_verify_expired_token_raises_401():
    token = _make_token(expires_in=-10)
    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt(token)
    assert excinfo.value.status_code == 401
    assert "expired" in excinfo.value.detail.lower()


def test_verify_wrong_issuer_raises_401():
    token = _make_token(issuer="https://attacker.example.com/auth/v1")
    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt(token)
    assert excinfo.value.status_code == 401
    assert "issuer" in excinfo.value.detail.lower()


def test_verify_wrong_audience_raises_401():
    token = _make_token(audience="not-authenticated")
    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt(token)
    assert excinfo.value.status_code == 401
    assert "audience" in excinfo.value.detail.lower()


def test_verify_bad_signature_raises_401():
    token = _make_token(secret="some-other-secret")
    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt(token)
    assert excinfo.value.status_code == 401


def test_verify_garbage_token_raises_401():
    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt("not.a.real.jwt")
    assert excinfo.value.status_code == 401


def test_verify_empty_token_raises_401():
    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt("")
    assert excinfo.value.status_code == 401


def test_verify_without_config_raises_500(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(settings, "supabase_jwks_url", "")
    auth._reset_jwks_cache()
    token = _make_token()
    with pytest.raises(HTTPException) as excinfo:
        auth.verify_supabase_jwt(token)
    assert excinfo.value.status_code == 500


@pytest.mark.asyncio
async def test_get_current_user_returns_payload_when_token_valid():
    token = _make_token()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    payload = await auth.get_current_user(credentials=creds)
    assert payload is not None
    assert payload["sub"] == "user-uuid-123"


@pytest.mark.asyncio
async def test_get_current_user_returns_none_in_dev_when_missing(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    payload = await auth.get_current_user(credentials=None)
    assert payload is None


@pytest.mark.asyncio
async def test_get_current_user_raises_in_production_when_missing(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    with pytest.raises(HTTPException) as excinfo:
        await auth.get_current_user(credentials=None)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_require_current_user_always_requires_token():
    with pytest.raises(HTTPException) as excinfo:
        await auth.require_current_user(credentials=None)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_require_current_user_accepts_valid_token():
    token = _make_token()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    payload = await auth.require_current_user(credentials=creds)
    assert payload["sub"] == "user-uuid-123"
