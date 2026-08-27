from datetime import date
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.health import HealthRecord, HealthRecordType


async def list_health_records(
    db: AsyncSession,
    jzd_id: int,
    livestock_id: Optional[int] = None,
    record_type: Optional[HealthRecordType] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[HealthRecord], int]:
    q = (
        select(HealthRecord)
        .where(HealthRecord.jzd_id == jzd_id)
        .options(
            selectinload(HealthRecord.livestock),
            selectinload(HealthRecord.veterinarian),
        )
    )
    if livestock_id:
        q = q.where(HealthRecord.livestock_id == livestock_id)
    if record_type:
        q = q.where(HealthRecord.record_type == record_type)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(HealthRecord.record_date.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = list((await db.execute(q)).scalars().all())
    return rows, total


async def get_health_record(
    db: AsyncSession, record_id: int, jzd_id: int
) -> Optional[HealthRecord]:
    result = await db.execute(
        select(HealthRecord)
        .where(HealthRecord.id == record_id, HealthRecord.jzd_id == jzd_id)
        .options(selectinload(HealthRecord.livestock), selectinload(HealthRecord.veterinarian))
    )
    return result.scalar_one_or_none()


async def create_health_record(
    db: AsyncSession,
    jzd_id: int,
    livestock_id: int,
    record_type: HealthRecordType,
    record_date: date,
    veterinarian_id: Optional[int] = None,
    diagnosis: Optional[str] = None,
    treatment: Optional[str] = None,
    medication: Optional[str] = None,
    dosage: Optional[str] = None,
    next_checkup_date: Optional[date] = None,
    temperature: Optional[float] = None,
    weight_at_record: Optional[float] = None,
    notes: Optional[str] = None,
) -> HealthRecord:
    record = HealthRecord(
        jzd_id=jzd_id,
        livestock_id=livestock_id,
        record_type=record_type,
        record_date=record_date,
        veterinarian_id=veterinarian_id,
        diagnosis=diagnosis,
        treatment=treatment,
        medication=medication,
        dosage=dosage,
        next_checkup_date=next_checkup_date,
        temperature=temperature,
        weight_at_record=weight_at_record,
        notes=notes,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def update_health_record(
    db: AsyncSession,
    record: HealthRecord,
    **fields,
) -> HealthRecord:
    for k, v in fields.items():
        if hasattr(record, k):
            setattr(record, k, v)
    await db.commit()
    await db.refresh(record)
    return record


async def delete_health_record(db: AsyncSession, record: HealthRecord) -> None:
    await db.delete(record)
    await db.commit()
