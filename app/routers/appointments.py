from datetime import date, time
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.livestock import Livestock, LivestockStatus
from app.models.user import AppUser, UserRole
from app.services.appointment import (
    create_appointment,
    delete_appointment,
    get_appointment,
    list_appointments,
    update_appointment_status,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])
templates = Jinja2Templates(directory="app/templates")


def _jzd_scope(user: AppUser) -> Optional[int]:
    return None if user.role.is_cross_jzd_reader else user.jzd_id


@router.get("", response_class=HTMLResponse)
async def appts_list(
    request: Request,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = 1,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = _jzd_scope(current_user) or current_user.jzd_id
    status_enum = AppointmentStatus(status) if status else None
    appts, total = await list_appointments(
        db, jzd_id, status=status_enum, from_date=from_date, to_date=to_date, page=page
    )
    return templates.TemplateResponse(
        "appointments/list.html",
        {
            "request": request,
            "current_user": current_user,
            "appts": appts,
            "total": total,
            "page": page,
            "status": status,
            "from_date": from_date,
            "to_date": to_date,
            "statuses": [s.value for s in AppointmentStatus],
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def appt_new_form(
    request: Request,
    livestock_id: Optional[int] = None,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = current_user.jzd_id
    q = select(Livestock).where(Livestock.jzd_id == jzd_id, Livestock.status == LivestockStatus.ACTIVE)
    animals = list((await db.execute(q)).scalars().all())
    return templates.TemplateResponse(
        "appointments/form.html",
        {
            "request": request,
            "current_user": current_user,
            "appt": None,
            "animals": animals,
            "preselected_livestock_id": livestock_id,
            "types": [t.value for t in AppointmentType],
            "errors": [],
        },
    )


@router.post("/new", response_class=HTMLResponse)
async def appt_new_submit(
    request: Request,
    livestock_id: int = Form(...),
    appointment_type: str = Form(...),
    scheduled_date: date = Form(...),
    scheduled_time: time = Form(...),
    duration_minutes: int = Form(60),
    notes: Optional[str] = Form(None),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = current_user.jzd_id
    errors = []
    if not jzd_id:
        errors.append("No JZD context")

    if errors:
        q = select(Livestock).where(Livestock.jzd_id == jzd_id, Livestock.status == LivestockStatus.ACTIVE)
        animals = list((await db.execute(q)).scalars().all())
        return templates.TemplateResponse(
            "appointments/form.html",
            {"request": request, "current_user": current_user, "appt": None, "animals": animals,
             "types": [t.value for t in AppointmentType], "errors": errors},
        )

    appt = await create_appointment(
        db, jzd_id=jzd_id, livestock_id=livestock_id,
        appointment_type=AppointmentType(appointment_type),
        scheduled_date=scheduled_date, scheduled_time=scheduled_time,
        requester_id=current_user.id, duration_minutes=duration_minutes, notes=notes,
    )
    return RedirectResponse(f"/appointments/{appt.id}", status_code=303)


@router.get("/{appt_id}", response_class=HTMLResponse)
async def appt_detail(
    request: Request,
    appt_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = _jzd_scope(current_user) or current_user.jzd_id
    appt = await get_appointment(db, appt_id, jzd_id)
    if not appt:
        raise HTTPException(404)
    return templates.TemplateResponse(
        "appointments/detail.html",
        {"request": request, "current_user": current_user, "appt": appt,
         "statuses": [s.value for s in AppointmentStatus]},
    )


@router.post("/{appt_id}/status", response_class=HTMLResponse)
async def appt_update_status(
    request: Request,
    appt_id: int,
    new_status: str = Form(...),
    cancellation_reason: Optional[str] = Form(None),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = _jzd_scope(current_user) or current_user.jzd_id
    appt = await get_appointment(db, appt_id, jzd_id)
    if not appt:
        raise HTTPException(404)
    await update_appointment_status(db, appt, AppointmentStatus(new_status), cancellation_reason)
    return RedirectResponse(f"/appointments/{appt_id}", status_code=303)


@router.post("/{appt_id}/delete")
async def appt_delete(
    appt_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN):
        raise HTTPException(403)
    jzd_id = _jzd_scope(current_user) or current_user.jzd_id
    appt = await get_appointment(db, appt_id, jzd_id)
    if not appt:
        raise HTTPException(404)
    await delete_appointment(db, appt)
    return RedirectResponse("/appointments", status_code=303)
