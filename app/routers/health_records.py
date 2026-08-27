from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.health import HealthRecord, HealthRecordType
from app.models.livestock import Livestock, LivestockStatus
from app.models.user import AppUser, UserRole
from app.services.health import (
    create_health_record,
    delete_health_record,
    get_health_record,
    list_health_records,
    update_health_record,
)

router = APIRouter(prefix="/health", tags=["health"])
templates = Jinja2Templates(directory="app/templates")


def _require_vet(user: AppUser):
    allowed = {UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.VETERINARIAN}
    if user.role not in allowed:
        raise HTTPException(403)


@router.get("", response_class=HTMLResponse)
async def health_list(
    request: Request,
    livestock_id: Optional[int] = None,
    record_type: Optional[str] = None,
    page: int = 1,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = current_user.jzd_id or 0
    rtype = HealthRecordType(record_type) if record_type else None
    records, total = await list_health_records(db, jzd_id, livestock_id=livestock_id, record_type=rtype, page=page)
    return templates.TemplateResponse(
        "health_records/list.html",
        {
            "request": request, "current_user": current_user,
            "records": records, "total": total, "page": page,
            "livestock_id": livestock_id, "record_type": record_type,
            "types": [t.value for t in HealthRecordType],
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def health_new_form(
    request: Request,
    livestock_id: Optional[int] = None,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_vet(current_user)
    jzd_id = current_user.jzd_id
    animals = list(
        (await db.execute(
            select(Livestock).where(Livestock.jzd_id == jzd_id, Livestock.status == LivestockStatus.ACTIVE)
        )).scalars().all()
    )
    return templates.TemplateResponse(
        "health_records/form.html",
        {
            "request": request, "current_user": current_user,
            "record": None, "animals": animals,
            "preselected_livestock_id": livestock_id,
            "types": [t.value for t in HealthRecordType],
            "errors": [],
        },
    )


@router.post("/new")
async def health_new_submit(
    request: Request,
    livestock_id: int = Form(...),
    record_type: str = Form(...),
    record_date: date = Form(...),
    diagnosis: Optional[str] = Form(None),
    treatment: Optional[str] = Form(None),
    medication: Optional[str] = Form(None),
    dosage: Optional[str] = Form(None),
    next_checkup_date: Optional[date] = Form(None),
    temperature: Optional[float] = Form(None),
    weight_at_record: Optional[float] = Form(None),
    notes: Optional[str] = Form(None),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_vet(current_user)
    jzd_id = current_user.jzd_id or 0
    record = await create_health_record(
        db, jzd_id=jzd_id, livestock_id=livestock_id,
        record_type=HealthRecordType(record_type),
        record_date=record_date,
        veterinarian_id=current_user.id,
        diagnosis=diagnosis, treatment=treatment,
        medication=medication, dosage=dosage,
        next_checkup_date=next_checkup_date,
        temperature=temperature, weight_at_record=weight_at_record,
        notes=notes,
    )
    return RedirectResponse(f"/health/{record.id}", status_code=303)


@router.get("/{record_id}", response_class=HTMLResponse)
async def health_detail(
    request: Request,
    record_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = current_user.jzd_id or 0
    record = await get_health_record(db, record_id, jzd_id)
    if not record:
        raise HTTPException(404)
    return templates.TemplateResponse(
        "health_records/detail.html",
        {"request": request, "current_user": current_user, "record": record},
    )


@router.get("/{record_id}/edit", response_class=HTMLResponse)
async def health_edit_form(
    request: Request,
    record_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_vet(current_user)
    jzd_id = current_user.jzd_id or 0
    record = await get_health_record(db, record_id, jzd_id)
    if not record:
        raise HTTPException(404)
    animals = list(
        (await db.execute(
            select(Livestock).where(Livestock.jzd_id == jzd_id, Livestock.status == LivestockStatus.ACTIVE)
        )).scalars().all()
    )
    return templates.TemplateResponse(
        "health_records/form.html",
        {
            "request": request, "current_user": current_user,
            "record": record, "animals": animals,
            "preselected_livestock_id": record.livestock_id,
            "types": [t.value for t in HealthRecordType],
            "errors": [],
        },
    )


@router.post("/{record_id}/edit")
async def health_edit_submit(
    request: Request,
    record_id: int,
    livestock_id: int = Form(...),
    record_type: str = Form(...),
    record_date: date = Form(...),
    diagnosis: Optional[str] = Form(None),
    treatment: Optional[str] = Form(None),
    medication: Optional[str] = Form(None),
    dosage: Optional[str] = Form(None),
    next_checkup_date: Optional[date] = Form(None),
    temperature: Optional[float] = Form(None),
    weight_at_record: Optional[float] = Form(None),
    notes: Optional[str] = Form(None),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_vet(current_user)
    jzd_id = current_user.jzd_id or 0
    record = await get_health_record(db, record_id, jzd_id)
    if not record:
        raise HTTPException(404)
    await update_health_record(
        db, record,
        record_type=HealthRecordType(record_type),
        record_date=record_date,
        diagnosis=diagnosis, treatment=treatment,
        medication=medication, dosage=dosage,
        next_checkup_date=next_checkup_date,
        temperature=temperature, weight_at_record=weight_at_record,
        notes=notes,
    )
    return RedirectResponse(f"/health/{record_id}", status_code=303)


@router.post("/{record_id}/delete")
async def health_delete(
    record_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_vet(current_user)
    jzd_id = current_user.jzd_id or 0
    record = await get_health_record(db, record_id, jzd_id)
    if not record:
        raise HTTPException(404)
    await delete_health_record(db, record)
    return RedirectResponse("/health", status_code=303)
