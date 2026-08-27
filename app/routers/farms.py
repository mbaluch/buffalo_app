from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import AppUser, UserRole
from app.schemas.farm import FarmCreate, FarmUpdate
from app.services.farm import create_farm, get_farm, get_farms, update_farm
from app.services.user import get_all_users

router = APIRouter(prefix="/farms", tags=["farms"])
templates = Jinja2Templates(directory="app/templates")


def _jzd_scope(user: AppUser) -> int | None:
    if user.role == UserRole.SUPER_ADMIN:
        return None
    return user.jzd_id


@router.get("", response_class=HTMLResponse)
async def list_farms(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    farms = await get_farms(db, jzd_id=_jzd_scope(current_user))
    return templates.TemplateResponse(
        "farms/list.html",
        {"request": request, "current_user": current_user, "farms": farms},
    )


@router.get("/new", response_class=HTMLResponse)
async def new_farm_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN):
        return RedirectResponse("/farms", status_code=status.HTTP_302_FOUND)
    owners = await get_all_users(db, jzd_id=current_user.jzd_id)
    return templates.TemplateResponse(
        "farms/form.html",
        {"request": request, "current_user": current_user, "farm": None,
         "owners": owners, "errors": []},
    )


@router.post("/new")
async def create_farm_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    name: str = Form(...),
    registration_number: str = Form(""),
    address: str = Form(""),
    city: str = Form(""),
    postal_code: str = Form(""),
    latitude: float = Form(...),
    longitude: float = Form(...),
    contact_phone: str = Form(""),
    owner_id: str = Form(""),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN):
        return RedirectResponse("/farms", status_code=status.HTTP_302_FOUND)

    errors = []
    try:
        data = FarmCreate(
            name=name,
            registration_number=registration_number or None,
            address=address or None,
            city=city or None,
            postal_code=postal_code or None,
            latitude=latitude,
            longitude=longitude,
            contact_phone=contact_phone or None,
            owner_id=int(owner_id) if owner_id else None,
        )
        await create_farm(current_user.jzd_id, data, db)
        return RedirectResponse("/farms", status_code=status.HTTP_302_FOUND)
    except Exception as exc:
        errors.append(str(exc))
        owners = await get_all_users(db, jzd_id=current_user.jzd_id)
        return templates.TemplateResponse(
            "farms/form.html",
            {"request": request, "current_user": current_user, "farm": None,
             "owners": owners, "errors": errors},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


@router.get("/{farm_id}/edit", response_class=HTMLResponse)
async def edit_farm_form(
    farm_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN):
        return RedirectResponse("/farms", status_code=status.HTTP_302_FOUND)
    farm = await get_farm(farm_id, db)
    if not farm or (current_user.jzd_id and farm.jzd_id != current_user.jzd_id):
        return RedirectResponse("/farms", status_code=status.HTTP_302_FOUND)
    owners = await get_all_users(db, jzd_id=farm.jzd_id)
    return templates.TemplateResponse(
        "farms/form.html",
        {"request": request, "current_user": current_user, "farm": farm,
         "owners": owners, "errors": []},
    )


@router.post("/{farm_id}/edit")
async def update_farm_submit(
    farm_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    name: str = Form(...),
    registration_number: str = Form(""),
    address: str = Form(""),
    city: str = Form(""),
    postal_code: str = Form(""),
    latitude: float = Form(...),
    longitude: float = Form(...),
    contact_phone: str = Form(""),
    owner_id: str = Form(""),
    is_active: str = Form("on"),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN):
        return RedirectResponse("/farms", status_code=status.HTTP_302_FOUND)
    farm = await get_farm(farm_id, db)
    if not farm or (current_user.jzd_id and farm.jzd_id != current_user.jzd_id):
        return RedirectResponse("/farms", status_code=status.HTTP_302_FOUND)

    errors = []
    try:
        data = FarmUpdate(
            name=name,
            registration_number=registration_number or None,
            address=address or None,
            city=city or None,
            postal_code=postal_code or None,
            latitude=latitude,
            longitude=longitude,
            contact_phone=contact_phone or None,
            owner_id=int(owner_id) if owner_id else None,
            is_active=(is_active == "on"),
        )
        await update_farm(farm, data, db)
        return RedirectResponse("/farms", status_code=status.HTTP_302_FOUND)
    except Exception as exc:
        errors.append(str(exc))
        owners = await get_all_users(db, jzd_id=farm.jzd_id)
        return templates.TemplateResponse(
            "farms/form.html",
            {"request": request, "current_user": current_user, "farm": farm,
             "owners": owners, "errors": errors},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
