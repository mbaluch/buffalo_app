from datetime import date, time
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.livestock import Livestock


async def list_appointments(
    db: AsyncSession,
    jzd_id: int,
    livestock_id: Optional[int] = None,
    status: Optional[AppointmentStatus] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Appointment], int]:
    q = (
        select(Appointment)
        .where(Appointment.jzd_id == jzd_id)
        .options(
            selectinload(Appointment.livestock),
            selectinload(Appointment.requester),
            selectinload(Appointment.assignee),
        )
    )
    if livestock_id:
        q = q.where(Appointment.livestock_id == livestock_id)
    if status:
        q = q.where(Appointment.status == status)
    if from_date:
        q = q.where(Appointment.scheduled_date >= from_date)
    if to_date:
        q = q.where(Appointment.scheduled_date <= to_date)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(Appointment.scheduled_date, Appointment.scheduled_time)
    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = list((await db.execute(q)).scalars().all())
    return rows, total


async def get_appointment(db: AsyncSession, appointment_id: int, jzd_id: int) -> Optional[Appointment]:
    result = await db.execute(
        select(Appointment)
        .where(Appointment.id == appointment_id, Appointment.jzd_id == jzd_id)
        .options(
            selectinload(Appointment.livestock),
            selectinload(Appointment.requester),
            selectinload(Appointment.assignee),
        )
    )
    return result.scalar_one_or_none()


async def create_appointment(
    db: AsyncSession,
    jzd_id: int,
    livestock_id: int,
    appointment_type: AppointmentType,
    scheduled_date: date,
    scheduled_time: time,
    requester_id: int,
    duration_minutes: int = 60,
    assignee_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Appointment:
    appt = Appointment(
        jzd_id=jzd_id,
        livestock_id=livestock_id,
        appointment_type=appointment_type,
        scheduled_date=scheduled_date,
        scheduled_time=scheduled_time,
        requester_id=requester_id,
        duration_minutes=duration_minutes,
        assignee_id=assignee_id,
        notes=notes,
    )
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return appt


async def update_appointment_status(
    db: AsyncSession,
    appointment: Appointment,
    new_status: AppointmentStatus,
    cancellation_reason: Optional[str] = None,
) -> Appointment:
    appointment.status = new_status
    if cancellation_reason:
        appointment.cancellation_reason = cancellation_reason
    await db.commit()
    await db.refresh(appointment)
    return appointment


async def delete_appointment(db: AsyncSession, appointment: Appointment) -> None:
    await db.delete(appointment)
    await db.commit()
