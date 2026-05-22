"""Create or refresh a dev user in Supabase + ``user_profiles``.

Usage:
    python scripts/create_dev_user.py
    python scripts/create_dev_user.py --email me@example.com --password 'SecurePw!'
    python scripts/create_dev_user.py --backfill   # only link existing UserProfiles to existing Supabase users by email

Requires ``SUPABASE_URL`` and ``SUPABASE_SERVICE_ROLE_KEY`` in your ``.env``.
The service-role key is admin-level — keep it server-side only, never ship it
to the frontend.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from config import settings  # noqa: E402
from db.database import async_session  # noqa: E402
from db.models import UserProfile  # noqa: E402

DEFAULT_EMAIL = "dev@realestate.local"
DEFAULT_PASSWORD = "DevPassword123!"
DEFAULT_NAME = "Dev User"


async def _list_supabase_users(client: httpx.AsyncClient) -> list[dict]:
    """Return all Supabase auth users (paginated, but dev volume is tiny)."""
    response = await client.get("/auth/v1/admin/users", params={"page": 1, "per_page": 200})
    response.raise_for_status()
    body = response.json()
    return body.get("users") or body or []


async def _find_supabase_user_by_email(client: httpx.AsyncClient, email: str) -> dict | None:
    users = await _list_supabase_users(client)
    for user in users:
        if user.get("email", "").lower() == email.lower():
            return user
    return None


async def _create_supabase_user(
    client: httpx.AsyncClient,
    *,
    email: str,
    password: str,
    name: str,
) -> dict:
    response = await client.post(
        "/auth/v1/admin/users",
        json={
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"full_name": name, "source": "scripts/create_dev_user.py"},
        },
    )
    response.raise_for_status()
    return response.json()


async def _ensure_local_profile(supabase_user: dict, *, email: str, name: str) -> str:
    """Create or update the local UserProfile row, linking supabase_user_id."""
    sub = supabase_user.get("id") or supabase_user.get("user", {}).get("id")
    if not sub:
        raise RuntimeError(f"Supabase user response had no id: {supabase_user}")

    async with async_session() as db:
        existing = (
            await db.execute(select(UserProfile).where(UserProfile.email == email))
        ).scalar_one_or_none()

        if existing is None:
            profile = UserProfile(
                supabase_user_id=sub,
                name=name,
                email=email,
                role="buyer",
                budget_min=300_000,
                budget_max=600_000,
                timeline_days=90,
                preferred_types=["sfr", "condo"],
            )
            db.add(profile)
            await db.commit()
            await db.refresh(profile)
            print(f"Created UserProfile {profile.id} linked to supabase {sub}")
            return str(profile.id)

        existing.supabase_user_id = sub
        existing.name = name
        await db.commit()
        print(f"Updated existing UserProfile {existing.id} → supabase {sub}")
        return str(existing.id)


async def _backfill_only() -> None:
    """Link every local UserProfile to its Supabase user by matching email."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set for backfill."
        )

    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    async with httpx.AsyncClient(base_url=settings.supabase_url, headers=headers, timeout=20) as client:
        sb_users = {u["email"].lower(): u["id"] for u in await _list_supabase_users(client) if u.get("email")}

    async with async_session() as db:
        local = (await db.execute(select(UserProfile))).scalars().all()
        linked = 0
        skipped = 0
        for profile in local:
            sub = sb_users.get(profile.email.lower())
            if not sub:
                skipped += 1
                continue
            if profile.supabase_user_id == sub:
                continue
            profile.supabase_user_id = sub
            linked += 1
        await db.commit()
        print(
            f"Backfill complete: linked={linked}, already-linked={len(local) - linked - skipped}, "
            f"no-supabase-match={skipped}"
        )


async def main(args: argparse.Namespace) -> None:
    if args.backfill:
        await _backfill_only()
        return

    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env. "
            "See doc/SUPABASE_AUTH_SETUP.md."
        )

    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    async with httpx.AsyncClient(base_url=settings.supabase_url, headers=headers, timeout=20) as client:
        existing = await _find_supabase_user_by_email(client, args.email)
        if existing:
            print(f"Supabase user already exists: {existing['id']} ({args.email})")
            sb_user = existing
        else:
            sb_user = await _create_supabase_user(
                client,
                email=args.email,
                password=args.password,
                name=args.name,
            )
            print(f"Created Supabase user: {sb_user.get('id')} ({args.email})")

    await _ensure_local_profile(sb_user, email=args.email, name=args.name)
    print()
    print("=========================================================")
    print(" Dev credentials")
    print("---------------------------------------------------------")
    print(f"  Email:    {args.email}")
    print(f"  Password: {args.password}")
    print("  Sign in at http://localhost:5173/signin")
    print("=========================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Link every existing UserProfile.email to a Supabase user, no creation.",
    )
    asyncio.run(main(parser.parse_args()))
