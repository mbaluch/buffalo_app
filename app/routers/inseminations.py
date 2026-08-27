from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.insemination import InseminationMethod, InseminationRecord, InseminationStatus
from app.models.livestock import Livestock, LivestockSex, LivestockStatus
from app.models.user import AppUser, UserRole
from app.services.insemination import (
    confirm_pregnancy,
    list_inseminations,
    mark_insemination_failed,
    record_calving,
    record_insemination,
)

router = APIRouter(prefix="/inseminations", tags=["inseminations"])
templates = Jinja2Templates(directory="app/templates")


def _require_insem_role(user: AppUser):
    allowed = {UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.INSEMINATOR, UserRole.SPERM_COLLECTOR}
    if user.role not in allowed:
        raise HTTPException(403, "Insufficient permissions")


def _require_vet_role(user: AppUser):
    allowed = {UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.VETERINARIAN}
    if user.role not in allowed:
        raise HTTPException(403, "Insufficient permissions")


@router.get("", response_class=HTMLResponse)
async def insem_list(
    request: Request,
    cow_id: Optional[int] = None,
    page: int = 1,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = current_user.jzd_id or 0
    records, total = await list_inseminations(db, jzd_id, cow_id=cow_id, page=page)
    return templates.TemplateResponse(
        "inseminations/list.html",
        {"request": request, "current_user": current_user, "records": records,
         "total": total, "page": page, "cow_id": cow_id},
    )


@router.get("/new", response_class=HTMLResponse)
async def insem_new_form(
    request: Request,
    cow_id: Optional[int] = None,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_insem_role(current_user)
    jzd_id = current_user.jzd_id
    cows_q = select(Livestock).where(
        Livestock.jzd_id == jzd_id,
        Livestock.sex == LivestockSex.FEMALE,
        Livestock.status == LivestockStatus.ACTIVE,
        Livestock.is_available_for_breeding.is_(True),
    )
    cows = list((await db.execute(cows_q)).scalars().all())
    bulls_q = select(Livestock).where(
        Livestock.sex == LivestockSex.MALE,
        Livestock.status == LivestockStatus.ACTIVE,
    )
    bulls = list((await db.execute(bulls_q)).scalars().all())
    return templates.TemplateResponse(
        "inseminations/form.html",
        {
            "request": request, "current_user": current_user,
            "cows": cows, "bulls": bulls,
            "preselected_cow_id": cow_id,
            "methods": [m.value for m in InseminationMethod],
            "errors": [],
        },
    )


@router.post("/new", response_class=HTMLResponse)
async def insem_new_submit(
    request: Request,
    cow_id: int = Form(...),
    method: str = Form(...),
    insemination_date: date = Form(...),
    bull_id: Optional[int] = Form(None),
    notes: Optional[str] = Form(None),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_insem_role(current_user)
    jzd_id = current_user.jzd_id or 0
    record = await record_insemination(
        db, jzd_id=jzd_id, cow_id=cow_id,
        method=InseminationMethod(method),
        insemination_date=insemination_date,
        inseminator_id=current_user.id,
        bull_id=bull_id or None,
        notes=notes,
    )
    return RedirectResponse(f"/inseminations/{record.id}", status_code=303)


@router.get("/{record_id}", response_class=HTMLResponse)
async def insem_detail(
    request: Request,
    record_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = current_user.jzd_id or 0
    records, _ = await list_inseminations(db, jzd_id)
    record = next((r for r in records if r.id == record_id), None)
    if not record:
        raise HTTPException(404)
    return templates.TemplateResponse(
        "inseminations/detail.html",
        {"request": request, "current_user": current_user, "record": record,
         "can_confirm": current_user.role in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.VETERINARIAN)},
    )


@router.post("/{record_id}/confirm-pregnancy")
async def insem_confirm_pregnancy(
    record_id: int,
    confirmed_date: date = Form(...),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_vet_role(current_user)
    jzd_id = current_user.jzd_id or 0
    records, _ = await list_inseminations(db, jzd_id)
    record = next((r for r in records if r.id == record_id), None)
    if not record:
        raise HTTPException(404)
    await confirm_pregnancy(db, record, confirmed_date, current_user.id)
    return RedirectResponse(f"/inseminations/{record_id}", status_code=303)


@router.post("/{record_id}/mark-failed")
async def insem_mark_failed(
    record_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_vet_role(current_user)
    jzd_id = current_user.jzd_id or 0
    records, _ = await list_inseminations(db, jzd_id)
    record = next((r for r in records if r.id == record_id), None)
    if not record:
        raise HTTPException(404)
    await mark_insemination_failed(db, record)
    return RedirectResponse(f"/inseminations/{record_id}", status_code=303)
