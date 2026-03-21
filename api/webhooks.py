"""Webhook endpoints for external service callbacks."""

import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.database import get_db
from db.models import MiroFishReport
from services.event_store import EventStore
from services.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _verify_hmac(body: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    if not secret:
        return True  # Skip verification if no secret configured
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/mirofish")
async def mirofish_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_mirofish_signature: str = Header(default=""),
):
    """Idempotent MiroFish simulation completion callback.

    The MiroFish backend calls this when a simulation finishes.
    Uses HMAC verification and idempotency based on report ID.
    """
    body = await request.body()

    # Verify HMAC signature
    if settings.mirofish_webhook_secret:
        if not _verify_hmac(body, x_mirofish_signature, settings.mirofish_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")

    import json
    data = json.loads(body)
    report_id = data.get("report_id")
    if not report_id:
        raise HTTPException(status_code=400, detail="Missing report_id")

    # Idempotency check
    existing = await db.execute(
        select(MiroFishReport).where(MiroFishReport.id == report_id)
    )
    report = existing.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.status == "completed":
        logger.info("webhook.mirofish.idempotent_skip", report_id=report_id)
        return {"status": "already_completed", "report_id": report_id}

    # Update report with results
    report.report_json = data.get("result", {})
    report.status = "completed"

    event_store = EventStore(db)
    await event_store.append(
        event_type="report.completed",
        aggregate_type="report",
        aggregate_id=report_id,
        payload={"user_id": report.user_id},
        actor_type="system",
        actor_id="mirofish",
    )

    await db.commit()

    logger.info("webhook.mirofish.completed", report_id=report_id, user_id=report.user_id)
    return {"status": "completed", "report_id": report_id}
