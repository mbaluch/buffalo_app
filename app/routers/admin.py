from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_super_admin
from app.models.user import AppUser, UserRole
from app.schemas.jzd import JzdCreate, JzdSettingsSchema, JzdUpdate
from app.schemas.user import UserCreate, UserUpdate
from app.services.jzd import create_jzd, get_all_jzds, get_jzd, update_jzd
from app.services.user import count_users_per_jzd, create_user, get_all_users, get_user, update_user

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
):
    jzds = await get_all_jzds(db)
    users = await get_all_users(db)
    user_counts = await count_users_per_jzd(db)
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "jzds": jzds,
            "users": users,
            "user_counts": user_counts,
            "total_jzds": len(jzds),
            "total_users": len(users),
            "active_jzds": sum(1 for j in jzds if j.is_active),
        },
    )


# ── JZD management ───────────────────────────────────────────────────────────

@router.get("/jzds", response_class=HTMLResponse)
async def list_jzds(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
):
    jzds = await get_all_jzds(db)
    user_counts = await count_users_per_jzd(db)
    return templates.TemplateResponse(
        "admin/jzds/list.html",
        {"request": request, "current_user": current_user,
         "jzds": jzds, "user_counts": user_counts},
    )


@router.get("/jzds/new", response_class=HTMLResponse)
async def new_jzd_form(
    request: Request,
    current_user: AppUser = Depends(require_super_admin),
):
    return templates.TemplateResponse(
        "admin/jzds/form.html",
        {"request": request, "current_user": current_user, "jzd": None, "errors": []},
    )


@router.post("/jzds/new")
async def create_jzd_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
    registration_number: str = Form(...),
    name: str = Form(...),
    address: str = Form(""),
    city: str = Form(""),
    postal_code: str = Form(""),
    contact_phone: str = Form(""),
    contact_email: str = Form(""),
    gestation_days: int = Form(283),
    recovery_days: int = Form(60),
):
    errors = []
    try:
        data = JzdCreate(
            registration_number=registration_number,
            name=name,
            address=address or None,
            city=city or None,
            postal_code=postal_code or None,
            contact_phone=contact_phone or None,
            contact_email=contact_email or None,
            settings=JzdSettingsSchema(
                gestation_days=gestation_days,
                recovery_days=recovery_days,
            ),
        )
        await create_jzd(data, db)
        return RedirectResponse("/admin/jzds", status_code=status.HTTP_302_FOUND)
    except Exception as exc:
        errors.append(str(exc))
        return templates.TemplateResponse(
            "admin/jzds/form.html",
            {"request": request, "current_user": current_user, "jzd": None, "errors": errors},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


@router.get("/jzds/{jzd_id}/edit", response_class=HTMLResponse)
async def edit_jzd_form(
    jzd_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
):
    jzd = await get_jzd(jzd_id, db)
    if not jzd:
        return RedirectResponse("/admin/jzds", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        "admin/jzds/form.html",
        {"request": request, "current_user": current_user, "jzd": jzd, "errors": []},
    )


@router.post("/jzds/{jzd_id}/edit")
async def update_jzd_submit(
    jzd_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
    name: str = Form(...),
    address: str = Form(""),
    city: str = Form(""),
    postal_code: str = Form(""),
    contact_phone: str = Form(""),
    contact_email: str = Form(""),
    gestation_days: int = Form(283),
    recovery_days: int = Form(60),
    is_active: str = Form("on"),
):
    jzd = await get_jzd(jzd_id, db)
    if not jzd:
        return RedirectResponse("/admin/jzds", status_code=status.HTTP_302_FOUND)

    errors = []
    try:
        data = JzdUpdate(
            name=name,
            address=address or None,
            city=city or None,
            postal_code=postal_code or None,
            contact_phone=contact_phone or None,
            contact_email=contact_email or None,
            is_active=(is_active == "on"),
            settings=JzdSettingsSchema(
                gestation_days=gestation_days,
                recovery_days=recovery_days,
            ),
        )
        await update_jzd(jzd, data, db)
        return RedirectResponse("/admin/jzds", status_code=status.HTTP_302_FOUND)
    except Exception as exc:
        errors.append(str(exc))
        return templates.TemplateResponse(
            "admin/jzds/form.html",
            {"request": request, "current_user": current_user, "jzd": jzd, "errors": errors},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


# ── User management ──────────────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
async def list_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
):
    users = await get_all_users(db)
    return templates.TemplateResponse(
        "admin/users/list.html",
        {"request": request, "current_user": current_user, "users": users},
    )


@router.get("/users/new", response_class=HTMLResponse)
async def new_user_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
):
    jzds = await get_all_jzds(db)
    return templates.TemplateResponse(
        "admin/users/form.html",
        {
            "request": request,
            "current_user": current_user,
            "user": None,
            "jzds": jzds,
            "roles": [r for r in UserRole],
            "errors": [],
        },
    )


@router.post("/users/new")
async def create_user_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(""),
    last_name: str = Form(""),
    phone: str = Form(""),
    role: str = Form(...),
    jzd_id: str = Form(""),
):
    jzds = await get_all_jzds(db)
    errors = []
    try:
        data = UserCreate(
            username=username,
            email=email,
            password=password,
            first_name=first_name or None,
            last_name=last_name or None,
            phone=phone or None,
            role=UserRole(role),
            jzd_id=int(jzd_id) if jzd_id else None,
        )
        await create_user(data, db)
        return RedirectResponse("/admin/users", status_code=status.HTTP_302_FOUND)
    except Exception as exc:
        errors.append(str(exc))
        return templates.TemplateResponse(
            "admin/users/form.html",
            {
                "request": request,
                "current_user": current_user,
                "user": None,
                "jzds": jzds,
                "roles": [r for r in UserRole],
                "errors": errors,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


@router.get("/users/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_form(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
):
    user = await get_user(user_id, db)
    jzds = await get_all_jzds(db)
    if not user:
        return RedirectResponse("/admin/users", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        "admin/users/form.html",
        {
            "request": request,
            "current_user": current_user,
            "user": user,
            "jzds": jzds,
            "roles": [r for r in UserRole],
            "errors": [],
        },
    )


@router.post("/users/{user_id}/edit")
async def update_user_submit(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
    first_name: str = Form(""),
    last_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(...),
    role: str = Form(...),
    jzd_id: str = Form(""),
    is_active: str = Form("on"),
):
    user = await get_user(user_id, db)
    jzds = await get_all_jzds(db)
    if not user:
        return RedirectResponse("/admin/users", status_code=status.HTTP_302_FOUND)

    errors = []
    try:
        data = UserUpdate(
            first_name=first_name or None,
            last_name=last_name or None,
            phone=phone or None,
            email=email,
            role=UserRole(role),
            jzd_id=int(jzd_id) if jzd_id else None,
            is_active=(is_active == "on"),
        )
        await update_user(user, data, db)
        return RedirectResponse("/admin/users", status_code=status.HTTP_302_FOUND)
    except Exception as exc:
        errors.append(str(exc))
        return templates.TemplateResponse(
            "admin/users/form.html",
            {
                "request": request,
                "current_user": current_user,
                "user": user,
                "jzds": jzds,
                "roles": [r for r in UserRole],
                "errors": errors,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
