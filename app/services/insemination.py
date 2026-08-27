from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.insemination import InseminationMethod, InseminationRecord, InseminationStatus
from app.models.jzd import JzdSettings
from app.models.livestock import Livestock, PregnancyStatus


async def list_inseminations(
    db: AsyncSession,
    jzd_id: int,
    cow_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[InseminationRecord], int]:
    q = (
        select(InseminationRecord)
        .where(InseminationRecord.jzd_id == jzd_id)
        .options(
            selectinload(InseminationRecord.cow),
            selectinload(InseminationRecord.bull),
            selectinload(InseminationRecord.inseminator),
            selectinload(InseminationRecord.pregnancy_confirmed_by),
        )
    )
    if cow_id:
        q = q.where(InseminationRecord.cow_id == cow_id)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(InseminationRecord.insemination_date.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = list((await db.execute(q)).scalars().all())
    return rows, total


async def _get_settings(db: AsyncSession, jzd_id: int) -> JzdSettings:
    result = await db.execute(select(JzdSettings).where(JzdSettings.jzd_id == jzd_id))
    settings = result.scalar_one_or_none()
    return settings


async def record_insemination(
    db: AsyncSession,
    jzd_id: int,
    cow_id: int,
    method: InseminationMethod,
    insemination_date: date,
    inseminator_id: Optional[int] = None,
    bull_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> InseminationRecord:
    settings = await _get_settings(db, jzd_id)
    gestation_days = settings.gestation_days if settings else 283
    expected_calving = insemination_date + timedelta(days=gestation_days)

    record = InseminationRecord(
        jzd_id=jzd_id,
        cow_id=cow_id,
        bull_id=bull_id,
        inseminator_id=inseminator_id,
        method=method,
        insemination_date=insemination_date,
        expected_calving_date=expected_calving,
        status=InseminationStatus.PERFORMED,
        notes=notes,
    )
    db.add(record)

    # Mark cow as pregnant
    cow_result = await db.execute(select(Livestock).where(Livestock.id == cow_id))
    cow = cow_result.scalar_one()
    cow.pregnancy_status = PregnancyStatus.PREGNANT
    cow.expected_calving_date = expected_calving
    cow.is_available_for_breeding = False

    await db.commit()
    await db.refresh(record)
    return record


async def confirm_pregnancy(
    db: AsyncSession,
    record: InseminationRecord,
    confirmed_date: date,
    veterinarian_id: int,
) -> InseminationRecord:
    record.pregnancy_confirmed_date = confirmed_date
    record.pregnancy_confirmed_by_id = veterinarian_id
    record.status = InseminationStatus.CONFIRMED_PREGNANT
    await db.commit()
    await db.refresh(record)
    return record


async def record_calving(
    db: AsyncSession,
    record: InseminationRecord,
    calving_date: date,
    calf: Livestock,
    jzd_id: int,
) -> InseminationRecord:
    settings = await _get_settings(db, jzd_id)
    recovery_days = settings.recovery_days if settings else 60
    recovery_until = calving_date + timedelta(days=recovery_days)

    record.actual_calving_date = calving_date
    record.calf_id = calf.id
    record.status = InseminationStatus.CALVED

    # Update cow
    cow_result = await db.execute(select(Livestock).where(Livestock.id == record.cow_id))
    cow = cow_result.scalar_one()
    cow.pregnancy_status = PregnancyStatus.CALVED
    cow.last_calving_date = calving_date
    cow.recovery_until_date = recovery_until
    cow.is_available_for_breeding = False
    cow.expected_calving_date = None

    await db.commit()
    await db.refresh(record)
    return record


async def mark_insemination_failed(
    db: AsyncSession,
    record: InseminationRecord,
) -> InseminationRecord:
    record.status = InseminationStatus.FAILED

    cow_result = await db.execute(select(Livestock).where(Livestock.id == record.cow_id))
    cow = cow_result.scalar_one()
    cow.pregnancy_status = None
    cow.expected_calving_date = None
    cow.is_available_for_breeding = True

    await db.commit()
    await db.refresh(record)
    return record
