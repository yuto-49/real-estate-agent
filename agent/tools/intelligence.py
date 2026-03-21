"""Intelligence report tool handler — bridges MiroFish reports into agent context."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MiroFishReport


async def get_intelligence_report(
    db: AsyncSession,
    user_id: str,
    report_id: str | None = None,
    **_kwargs,
) -> dict:
    """Retrieve a completed intelligence report for use in negotiation strategy."""
    if report_id:
        result = await db.execute(
            select(MiroFishReport).where(
                MiroFishReport.id == report_id,
                MiroFishReport.status == "completed",
            )
        )
        report = result.scalar_one_or_none()
    else:
        # Get the most recent completed report for this user
        result = await db.execute(
            select(MiroFishReport)
            .where(
                MiroFishReport.user_id == user_id,
                MiroFishReport.status == "completed",
            )
            .order_by(MiroFishReport.created_at.desc())
            .limit(1)
        )
        report = result.scalar_one_or_none()

    if not report:
        return {"error": "No completed intelligence report found for this user"}

    report_data = report.report_json or {}
    return {
        "report_id": report.id,
        "user_id": report.user_id,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        **report_data,
    }
