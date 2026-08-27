from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.livestock import LivestockSex, LivestockStatus
from app.models.user import AppUser, UserRole
from app.schemas.livestock import LivestockCreate, LivestockSearchParams, LivestockUpdate
from app.services.appointment import list_appointments
from app.services.attribute import get_attribute_definitions, get_cattle_type
from app.services.farm import get_farms
from app.services.health import list_health_records
from app.services.insemination import list_inseminations
from app.services.livestock import (
    create_livestock,
    generate_registration_number,
    get_livestock,
    search_livestock,
    update_livestock,
)
from app.services.photo import delete_photo, upload_photo

router = APIRouter(prefix="/livestock", tags=["livestock"])
templates = Jinja2Templates(directory="app/templates")


def _jzd_scope(user: AppUser) -> int | None:
    """None = cross-JZD readable roles; int = own JZD only."""
    if user.role.is_cross_jzd_reader or user.role == UserRole.SUPER_ADMIN:
        return None
    return user.jzd_id


@router.get("", response_class=HTMLResponse)
async def list_livestock(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    sex: str = "",
    farm_id: str = "",
    available_for_breeding: str = "",
    breed: str = "",
    min_weight: str = "",
    max_weight: str = "",
    min_height: str = "",
    max_height: str = "",
    min_leg_length: str = "",
    max_leg_length: str = "",
    q: str = "",
    page: int = 1,
):
    params = LivestockSearchParams(
        sex=LivestockSex(sex) if sex else None,
        farm_id=int(farm_id) if farm_id else None,
        available_for_breeding=True if available_for_breeding == "1" else None,
        breed=breed or None,
        min_weight=float(min_weight) if min_weight else None,
        max_weight=float(max_weight) if max_weight else None,
        min_height=float(min_height) if min_height else None,
        max_height=float(max_height) if max_height else None,
        min_leg_length=float(min_leg_length) if min_leg_length else None,
        max_leg_length=float(max_leg_length) if max_leg_length else None,
        q=q or None,
        page=page,
    )

    livestock_list, total = await search_livestock(params, db, jzd_id=_jzd_scope(current_user))

    cattle_type = await get_cattle_type(db)
    attr_defs = await get_attribute_definitions(cattle_type.id, db)
    farms = await get_farms(db, jzd_id=current_user.jzd_id)
    breed_options = next(
        (a.enum_values for a in attr_defs if a.attribute_key == "breed"), []
    )

    total_pages = max(1, (total + params.page_size - 1) // params.page_size)

    return templates.TemplateResponse(
        "livestock/list.html",
        {
            "request": request,
            "current_user": current_user,
            "livestock_list": livestock_list,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "farms": farms,
            "breed_options": breed_options,
            "attr_defs": attr_defs,
            # pass current filters back for form persistence
            "filters": {
                "sex": sex, "farm_id": farm_id,
                "available_for_breeding": available_for_breeding,
                "breed": breed, "min_weight": min_weight, "max_weight": max_weight,
                "min_height": min_height, "max_height": max_height,
                "min_leg_length": min_leg_length, "max_leg_length": max_leg_length,
                "q": q,
            },
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_livestock_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.FARM_OWNER):
        return RedirectResponse("/livestock", status_code=status.HTTP_302_FOUND)

    cattle_type = await get_cattle_type(db)
    attr_defs = await get_attribute_definitions(cattle_type.id, db)
    farms = await get_farms(db, jzd_id=current_user.jzd_id)

    return templates.TemplateResponse(
        "livestock/form.html",
        {
            "request": request,
            "current_user": current_user,
            "animal": None,
            "attr_defs": attr_defs,
            "farms": farms,
            "errors": [],
        },
    )


@router.post("/new")
async def create_livestock_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.FARM_OWNER):
        return RedirectResponse("/livestock", status_code=status.HTTP_302_FOUND)

    form = await request.form()
    cattle_type = await get_cattle_type(db)
    attr_defs = await get_attribute_definitions(cattle_type.id, db)
    farms = await get_farms(db, jzd_id=current_user.jzd_id)

    reg_number = str(form.get("registration_number", "")).strip()
    if form.get("auto_generate") == "1" or not reg_number:
        reg_number = await generate_registration_number(current_user.jzd_id, db)

    # Collect dynamic attributes from form
    attributes: dict[str, Any] = {}
    for defn in attr_defs:
        raw = form.get(f"attr_{defn.attribute_key}", "")
        if raw:
            if defn.data_type.value in ("NUMBER", "DECIMAL"):
                try:
                    attributes[defn.attribute_key] = float(raw)
                except ValueError:
                    attributes[defn.attribute_key] = raw
            else:
                attributes[defn.attribute_key] = raw

    errors: list[str] = []
    try:
        data = LivestockCreate(
            farm_id=int(form.get("farm_id", 0)),
            registration_number=reg_number,
            name=str(form.get("name", "")) or None,
            sex=LivestockSex(form.get("sex", "FEMALE")),
            attributes=attributes,
            is_available_for_breeding=form.get("is_available_for_breeding") == "on",
        )
    except Exception as exc:
        errors.append(str(exc))
        return templates.TemplateResponse(
            "livestock/form.html",
            {"request": request, "current_user": current_user,
             "animal": None, "attr_defs": attr_defs, "farms": farms, "errors": errors},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    animal, val_errors = await create_livestock(data, current_user.jzd_id, current_user.id, db)
    if val_errors:
        return templates.TemplateResponse(
            "livestock/form.html",
            {"request": request, "current_user": current_user,
             "animal": None, "attr_defs": attr_defs, "farms": farms, "errors": val_errors},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return RedirectResponse(f"/livestock/{animal.id}", status_code=status.HTTP_302_FOUND)


@router.get("/{livestock_id}", response_class=HTMLResponse)
async def livestock_detail(
    livestock_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    animal = await get_livestock(livestock_id, db)
    if not animal:
        return RedirectResponse("/livestock", status_code=status.HTTP_302_FOUND)

    attr_defs = await get_attribute_definitions(animal.livestock_type_id, db)

    can_edit = current_user.role in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.FARM_OWNER)
    can_upload_photo = can_edit

    jzd_id = current_user.jzd_id or animal.jzd_id
    inseminations, _ = await list_inseminations(db, jzd_id, cow_id=livestock_id, page_size=5)
    health_records, _ = await list_health_records(db, jzd_id, livestock_id=livestock_id, page_size=5)
    appointments, _ = await list_appointments(db, jzd_id, livestock_id=livestock_id, page_size=5)

    return templates.TemplateResponse(
        "livestock/detail.html",
        {
            "request": request,
            "current_user": current_user,
            "animal": animal,
            "attr_defs": attr_defs,
            "can_edit": can_edit,
            "can_upload_photo": can_upload_photo,
            "inseminations": inseminations,
            "health_records": health_records,
            "appointments": appointments,
        },
    )


@router.get("/{livestock_id}/edit", response_class=HTMLResponse)
async def edit_livestock_form(
    livestock_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.FARM_OWNER):
        return RedirectResponse(f"/livestock/{livestock_id}", status_code=status.HTTP_302_FOUND)

    animal = await get_livestock(livestock_id, db)
    if not animal:
        return RedirectResponse("/livestock", status_code=status.HTTP_302_FOUND)

    cattle_type = await get_cattle_type(db)
    attr_defs = await get_attribute_definitions(cattle_type.id, db)
    farms = await get_farms(db, jzd_id=current_user.jzd_id)

    return templates.TemplateResponse(
        "livestock/form.html",
        {"request": request, "current_user": current_user,
         "animal": animal, "attr_defs": attr_defs, "farms": farms, "errors": []},
    )


@router.post("/{livestock_id}/edit")
async def update_livestock_submit(
    livestock_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.FARM_OWNER):
        return RedirectResponse(f"/livestock/{livestock_id}", status_code=status.HTTP_302_FOUND)

    animal = await get_livestock(livestock_id, db)
    if not animal:
        return RedirectResponse("/livestock", status_code=status.HTTP_302_FOUND)

    form = await request.form()
    attr_defs = await get_attribute_definitions(animal.livestock_type_id, db)
    farms = await get_farms(db, jzd_id=current_user.jzd_id)

    attributes: dict[str, Any] = dict(animal.attributes)
    for defn in attr_defs:
        raw = form.get(f"attr_{defn.attribute_key}", "")
        if raw:
            if defn.data_type.value in ("NUMBER", "DECIMAL"):
                try:
                    attributes[defn.attribute_key] = float(raw)
                except ValueError:
                    attributes[defn.attribute_key] = raw
            else:
                attributes[defn.attribute_key] = raw

    data = LivestockUpdate(
        farm_id=int(form.get("farm_id")) if form.get("farm_id") else None,
        name=str(form.get("name", "")) or None,
        status=LivestockStatus(form.get("status", animal.status.value)),
        attributes=attributes,
        is_available_for_breeding=form.get("is_available_for_breeding") == "on",
    )

    updated, errors = await update_livestock(animal, data, db)
    if errors:
        return templates.TemplateResponse(
            "livestock/form.html",
            {"request": request, "current_user": current_user,
             "animal": animal, "attr_defs": attr_defs, "farms": farms, "errors": errors},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return RedirectResponse(f"/livestock/{livestock_id}", status_code=status.HTTP_302_FOUND)


@router.post("/{livestock_id}/photos")
async def upload_livestock_photo(
    livestock_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    photo: UploadFile = File(...),
    make_primary: str = Form("off"),
):
    animal = await get_livestock(livestock_id, db)
    if not animal:
        return RedirectResponse("/livestock", status_code=status.HTTP_302_FOUND)

    data = await photo.read()
    errors = []
    try:
        await upload_photo(
            livestock=animal,
            data=data,
            mime_type=photo.content_type or "image/jpeg",
            original_filename=photo.filename or "",
            uploader_id=current_user.id,
            make_primary=(make_primary == "on"),
            db=db,
        )
    except ValueError as exc:
        errors.append(str(exc))

    return RedirectResponse(
        f"/livestock/{livestock_id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/{livestock_id}/photos/{photo_id}")
async def serve_photo(
    livestock_id: int,
    photo_id: int,
    db: AsyncSession = Depends(get_db),
    thumbnail: bool = False,
):
    animal = await get_livestock(livestock_id, db)
    if not animal:
        return Response(status_code=404)

    photo = next((p for p in animal.photos if p.id == photo_id), None)
    if not photo:
        return Response(status_code=404)

    data = photo.thumbnail_data if (thumbnail and photo.thumbnail_data) else photo.data
    return Response(content=data, media_type=photo.mime_type)


@router.get("/{livestock_id}/photos/{photo_id}/thumbnail")
async def serve_thumbnail(livestock_id: int, photo_id: int, db: AsyncSession = Depends(get_db)):
    return await serve_photo(livestock_id, photo_id, db, thumbnail=True)


@router.post("/{livestock_id}/photos/{photo_id}/delete")
async def delete_livestock_photo(
    livestock_id: int,
    photo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    animal = await get_livestock(livestock_id, db)
    if animal:
        await delete_photo(photo_id, animal, db)
    return RedirectResponse(f"/livestock/{livestock_id}", status_code=status.HTTP_302_FOUND)
