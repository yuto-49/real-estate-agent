"""Auth-focused unit and integration tests for Supabase-backed identity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.database import get_db
from db.models import UserProfile
from main import app
from middleware import auth as auth_mw
from middleware.auth import (
    AuthUser,
    _resolve_jwks_url,
    _resolve_supabase_issuer,
    resolve_or_create_user_profile,
    verify_access_token,
)


def _build_rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


def _encode_token(private_key, *, sub: str | None, email: str | None, issuer: str, exp_delta_sec: int = 60):
    payload = {
        "iss": issuer,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=exp_delta_sec),
    }
    if sub is not None:
        payload["sub"] = sub
    if email is not None:
        payload["email"] = email
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key", "alg": "RS256"})


class _FakeJWKClient:
    def __init__(self, public_key):
        self._public_key = public_key

    def get_signing_key_from_jwt(self, _token: str):
        return SimpleNamespace(key=self._public_key, algorithm_name="RS256")


@pytest.mark.asyncio
async def test_verify_access_token_valid(monkeypatch):
    issuer = "https://example.supabase.co/auth/v1"
    private_key, public_key = _build_rsa_keypair()
    token = _encode_token(private_key, sub="supa-user-1", email="owner@example.com", issuer=issuer)

    monkeypatch.setattr(auth_mw.settings, "supabase_jwt_issuer", issuer)
    monkeypatch.setattr(auth_mw, "_get_jwk_client", lambda: _FakeJWKClient(public_key))

    user = verify_access_token(token)
    assert user.sub == "supa-user-1"
    assert user.email == "owner@example.com"


@pytest.mark.asyncio
async def test_verify_access_token_expired(monkeypatch):
    issuer = "https://example.supabase.co/auth/v1"
    private_key, public_key = _build_rsa_keypair()
    token = _encode_token(
        private_key,
        sub="supa-user-1",
        email="owner@example.com",
        issuer=issuer,
        exp_delta_sec=-60,
    )

    monkeypatch.setattr(auth_mw.settings, "supabase_jwt_issuer", issuer)
    monkeypatch.setattr(auth_mw, "_get_jwk_client", lambda: _FakeJWKClient(public_key))

    with pytest.raises(HTTPException) as exc:
        verify_access_token(token)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Token expired"


@pytest.mark.asyncio
async def test_verify_access_token_wrong_issuer(monkeypatch):
    expected_issuer = "https://example.supabase.co/auth/v1"
    private_key, public_key = _build_rsa_keypair()
    token = _encode_token(
        private_key,
        sub="supa-user-1",
        email="owner@example.com",
        issuer="https://wrong.example/auth/v1",
    )

    monkeypatch.setattr(auth_mw.settings, "supabase_jwt_issuer", expected_issuer)
    monkeypatch.setattr(auth_mw, "_get_jwk_client", lambda: _FakeJWKClient(public_key))

    with pytest.raises(HTTPException) as exc:
        verify_access_token(token)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid access token"


@pytest.mark.asyncio
async def test_verify_access_token_bad_signature(monkeypatch):
    issuer = "https://example.supabase.co/auth/v1"
    private_key_1, public_key_1 = _build_rsa_keypair()
    private_key_2, _public_key_2 = _build_rsa_keypair()
    token = _encode_token(private_key_2, sub="supa-user-1", email="owner@example.com", issuer=issuer)

    monkeypatch.setattr(auth_mw.settings, "supabase_jwt_issuer", issuer)
    monkeypatch.setattr(auth_mw, "_get_jwk_client", lambda: _FakeJWKClient(public_key_1))

    with pytest.raises(HTTPException) as exc:
        verify_access_token(token)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid access token"


@pytest.mark.asyncio
async def test_verify_access_token_missing_sub(monkeypatch):
    issuer = "https://example.supabase.co/auth/v1"
    private_key, public_key = _build_rsa_keypair()
    token = _encode_token(private_key, sub=None, email="owner@example.com", issuer=issuer)

    monkeypatch.setattr(auth_mw.settings, "supabase_jwt_issuer", issuer)
    monkeypatch.setattr(auth_mw, "_get_jwk_client", lambda: _FakeJWKClient(public_key))

    with pytest.raises(HTTPException) as exc:
        verify_access_token(token)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Token missing subject"


def test_supabase_override_comments_fall_back_to_default(monkeypatch):
    monkeypatch.setattr(auth_mw.settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(
        auth_mw.settings,
        "supabase_jwt_issuer",
        "# Optional override; defaults to https://example.supabase.co/auth/v1",
    )
    monkeypatch.setattr(
        auth_mw.settings,
        "supabase_jwks_url",
        "# Optional override; defaults to https://example.supabase.co/auth/v1/.well-known/jwks.json",
    )

    assert _resolve_supabase_issuer() == "https://example.supabase.co/auth/v1"
    assert _resolve_jwks_url() == "https://example.supabase.co/auth/v1/.well-known/jwks.json"


@pytest.mark.asyncio
async def test_resolve_profile_by_supabase_user_id(db):
    user = UserProfile(
        name="Mapped User",
        email="mapped@example.com",
        role="buyer",
        supabase_user_id="supa-user-1",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    resolved = await resolve_or_create_user_profile(
        db,
        AuthUser(sub="supa-user-1", email="mapped@example.com", role="authenticated", claims={}),
    )
    assert resolved.id == user.id


@pytest.mark.asyncio
async def test_resolve_profile_claims_unmapped_email(db):
    user = UserProfile(
        name="Legacy User",
        email="legacy@example.com",
        role="buyer",
        supabase_user_id=None,
    )
    db.add(user)
    await db.commit()

    resolved = await resolve_or_create_user_profile(
        db,
        AuthUser(sub="supa-user-2", email="legacy@example.com", role="authenticated", claims={}),
    )
    assert resolved.email == "legacy@example.com"
    assert resolved.supabase_user_id == "supa-user-2"


@pytest.mark.asyncio
async def test_resolve_profile_auto_provisions(db):
    resolved = await resolve_or_create_user_profile(
        db,
        AuthUser(sub="supa-user-3", email="new.user@example.com", role="authenticated", claims={}),
    )
    assert resolved.supabase_user_id == "supa-user-3"
    assert resolved.email == "new.user@example.com"
    assert resolved.role == "buyer"
    assert resolved.name == "New User"


@pytest.mark.asyncio
async def test_resolve_profile_requires_email_claim(db):
    with pytest.raises(HTTPException) as exc:
        await resolve_or_create_user_profile(
            db,
            AuthUser(sub="supa-user-4", email=None, role="authenticated", claims={}),
        )
    assert exc.value.status_code == 400
    assert "email claim" in exc.value.detail


@pytest_asyncio.fixture
async def api_client(db_engine):
    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )

    async def _override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


def _valid_auth_user() -> AuthUser:
    return AuthUser(
        sub="supa-user-integration",
        email="integration@example.com",
        role="authenticated",
        claims={"sub": "supa-user-integration", "email": "integration@example.com"},
    )


@pytest.mark.asyncio
async def test_protected_route_requires_bearer(api_client):
    response = await api_client.get("/api/properties/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_rejects_invalid_bearer(monkeypatch, api_client):
    def _invalid(_token: str):
        raise HTTPException(status_code=401, detail="Invalid access token")

    monkeypatch.setattr(auth_mw, "verify_access_token", _invalid)
    response = await api_client.get(
        "/api/properties/",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_public_health_stays_open(api_client):
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_users_me_and_legacy_forbidden(monkeypatch, api_client):
    monkeypatch.setattr(auth_mw, "verify_access_token", lambda _token: _valid_auth_user())
    headers = {"Authorization": "Bearer valid-test-token"}

    me_resp = await api_client.get("/api/users/me", headers=headers)
    assert me_resp.status_code == 200
    me = me_resp.json()
    assert me["email"] == "integration@example.com"

    patch_resp = await api_client.patch("/api/users/me", headers=headers, json={"name": "Updated User"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated User"

    list_resp = await api_client.get("/api/users/", headers=headers)
    assert list_resp.status_code == 403

    create_resp = await api_client.post(
        "/api/users/",
        headers=headers,
        json={"name": "X", "email": "x@example.com"},
    )
    assert create_resp.status_code == 403

    delete_resp = await api_client.delete(f"/api/users/{me['id']}", headers=headers)
    assert delete_resp.status_code == 403


@pytest.mark.asyncio
async def test_report_generate_uses_token_identity_not_body(monkeypatch, api_client):
    monkeypatch.setattr(auth_mw, "verify_access_token", lambda _token: _valid_auth_user())

    async def _noop_report_workflow(*_args, **_kwargs):
        return None

    monkeypatch.setattr("api.reports._run_report_workflow", _noop_report_workflow)
    headers = {"Authorization": "Bearer valid-test-token"}

    response = await api_client.post(
        "/api/reports/generate",
        headers=headers,
        json={
            "question": "Should I buy now?",
            "user_id": "spoofed-user-id",
        },
    )
    assert response.status_code == 202
    payload = response.json()

    me = await api_client.get("/api/users/me", headers=headers)
    assert me.status_code == 200
    assert payload["user_id"] == me.json()["id"]
