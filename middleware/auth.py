"""JWT authentication middleware (placeholder — uses simple token validation)."""

import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings

security = HTTPBearer(auto_error=False)


def create_token(user_id: str, role: str = "buyer", expires_in: int = 86400) -> str:
    """Create a simple HMAC-signed token. Replace with proper JWT in production."""
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": int(time.time()) + expires_in,
    }
    payload_json = json.dumps(payload, sort_keys=True)
    secret = settings.anthropic_api_key or "dev-secret"
    sig = hmac.new(secret.encode(), payload_json.encode(), hashlib.sha256).hexdigest()[:32]
    import base64
    token = base64.urlsafe_b64encode(payload_json.encode()).decode() + "." + sig
    return token


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a token."""
    import base64
    parts = token.split(".")
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid token format")

    payload_b64, sig = parts
    payload_json = base64.urlsafe_b64decode(payload_b64).decode()
    secret = settings.anthropic_api_key or "dev-secret"
    expected_sig = hmac.new(secret.encode(), payload_json.encode(), hashlib.sha256).hexdigest()[:32]

    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    payload = json.loads(payload_json)
    if payload.get("exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> dict[str, Any] | None:
    """Extract user from auth header. Returns None if no auth (dev mode)."""
    if not credentials:
        if settings.environment == "development":
            return None  # Allow unauthenticated in dev
        raise HTTPException(status_code=401, detail="Authentication required")

    return decode_token(credentials.credentials)
