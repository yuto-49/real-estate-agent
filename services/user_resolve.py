"""Resolve an inbound user identifier to an internal ``UserProfile.id``.

The frontend's auth layer hands out Supabase auth ids (``user.id`` from
``useAuth``), but the rest of the backend keys everything on the internal
``UserProfile.id``. These are different values linked by the
``UserProfile.supabase_user_id`` column.

This helper bridges the two so onboarding endpoints can accept whatever the
signed-in client naturally has — the Supabase id — and still resolve (or
provision) the matching local profile.

Resolution order:
1. ``UserProfile.id == identifier``        (already an internal id)
2. ``UserProfile.supabase_user_id == identifier``  (a Supabase auth id)
3. ``UserProfile.email == email``          (link an existing profile by email)
4. If ``auto_create`` and an email is available, create a new profile linked
   to the Supabase id.

Raises :class:`LookupError` when none of the above resolves — callers turn
that into a 404 ``user_not_found``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserProfile


async def resolve_user_profile(
    db: AsyncSession,
    identifier: str,
    *,
    email: str | None = None,
    name: str | None = None,
    auto_create: bool = False,
) -> UserProfile:
    """Return the ``UserProfile`` for an internal id or Supabase auth id."""
    by_id = (
        await db.execute(select(UserProfile).where(UserProfile.id == identifier))
    ).scalar_one_or_none()
    if by_id is not None:
        return by_id

    by_sub = (
        await db.execute(
            select(UserProfile).where(UserProfile.supabase_user_id == identifier)
        )
    ).scalar_one_or_none()
    if by_sub is not None:
        return by_sub

    if email:
        by_email = (
            await db.execute(select(UserProfile).where(UserProfile.email == email))
        ).scalar_one_or_none()
        if by_email is not None:
            # Link the Supabase id onto the existing profile so future
            # lookups hit branch 2 directly.
            if by_email.supabase_user_id is None:
                by_email.supabase_user_id = identifier
            return by_email

    if auto_create and email:
        profile = UserProfile(
            supabase_user_id=identifier,
            name=name or email.split("@")[0],
            email=email,
            role="buyer",
        )
        db.add(profile)
        await db.flush()
        return profile

    raise LookupError("user_not_found")


async def resolve_user_id(
    db: AsyncSession,
    identifier: str,
    *,
    email: str | None = None,
    name: str | None = None,
    auto_create: bool = False,
) -> str:
    """Convenience wrapper returning just the internal ``UserProfile.id``."""
    profile = await resolve_user_profile(
        db, identifier, email=email, name=name, auto_create=auto_create
    )
    return profile.id


__all__ = ["resolve_user_profile", "resolve_user_id"]
