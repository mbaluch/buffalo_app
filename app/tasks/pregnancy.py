"""Daily Celery task — release cows from recovery after recovery_days elapsed."""

import asyncio
from datetime import date

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.livestock import Livestock, LivestockStatus, PregnancyStatus
from app.tasks.celery_app import celery_app


async def _release_recovered(session: AsyncSession) -> int:
    today = date.today()
    q = select(Livestock).where(
        and_(
            Livestock.status == LivestockStatus.ACTIVE,
            Livestock.pregnancy_status == PregnancyStatus.CALVED,
            Livestock.recovery_until_date != None,
            Livestock.recovery_until_date <= today,
        )
    )
    rows = list((await session.execute(q)).scalars().all())
    for cow in rows:
        cow.pregnancy_status = None
        cow.recovery_until_date = None
        cow.is_available_for_breeding = True
    await session.commit()
    return len(rows)


@celery_app.task(name="app.tasks.pregnancy.release_recovered_cows")
def release_recovered_cows() -> dict:
    async def _run():
        async with AsyncSessionLocal() as session:
            count = await _release_recovered(session)
        return {"released": count}

    return asyncio.get_event_loop().run_until_complete(_run())
