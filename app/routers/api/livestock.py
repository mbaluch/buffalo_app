from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import AppUser, UserRole
from app.schemas.livestock import (
    LivestockCreate,
    LivestockResponse,
    LivestockSearchParams,
    LivestockUpdate,
)
from app.services.livestock import (
    create_livestock,
    get_livestock,
    search_livestock,
    update_livestock,
)
from app.services.photo import delete_photo, upload_photo

router = APIRouter(prefix="/api/v1/livestock", tags=["api:livestock"])


def _jzd_scope(user: AppUser) -> int | None:
    if user.role.is_cross_jzd_reader or user.role == UserRole.SUPER_ADMIN:
        return None
    return user.jzd_id


@router.get("")
async def api_list_livestock(
    sex: str | None = Query(None),
    farm_id: int | None = Query(None),
    available_for_breeding: bool | None = Query(None),
    breed: str | None = Query(None),
    min_weight: float | None = Query(None),
    max_weight: float | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    from app.models.livestock import LivestockSex

    params = LivestockSearchParams(
        sex=LivestockSex(sex) if sex else None,
        farm_id=farm_id,
        available_for_breeding=available_for_breeding,
        breed=breed,
        min_weight=min_weight,
        max_weight=max_weight,
        q=q,
        page=page,
        page_size=page_size,
    )
    livestock_list, total = await search_livestock(params, db, jzd_id=_jzd_scope(current_user))
    return {
        "success": True,
        "data": [LivestockResponse.model_validate(a) for a in livestock_list],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        },
    }


@router.get("/{livestock_id}")
async def api_get_livestock(
    livestock_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    animal = await get_livestock(livestock_id, db)
    if not animal:
        raise HTTPException(status_code=404, detail="Not found")
    return {"success": True, "data": LivestockResponse.model_validate(animal)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def api_create_livestock(
    data: LivestockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.FARM_OWNER):
        raise HTTPException(status_code=403, detail="Forbidden")
    animal, errors = await create_livestock(data, current_user.jzd_id, current_user.id, db)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    return {"success": True, "data": LivestockResponse.model_validate(animal)}


@router.put("/{livestock_id}")
async def api_update_livestock(
    livestock_id: int,
    data: LivestockUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.FARM_OWNER):
        raise HTTPException(status_code=403, detail="Forbidden")
    animal = await get_livestock(livestock_id, db)
    if not animal:
        raise HTTPException(status_code=404, detail="Not found")
    updated, errors = await update_livestock(animal, data, db)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    return {"success": True, "data": LivestockResponse.model_validate(updated)}


@router.post("/{livestock_id}/photos", status_code=status.HTTP_201_CREATED)
async def api_upload_photo(
    livestock_id: int,
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.FARM_OWNER):
        raise HTTPException(status_code=403, detail="Forbidden")
    animal = await get_livestock(livestock_id, db)
    if not animal:
        raise HTTPException(status_code=404, detail="Not found")
    data = await photo.read()
    try:
        p = await upload_photo(
            livestock=animal,
            data=data,
            mime_type=photo.content_type or "image/jpeg",
            original_filename=photo.filename or "",
            uploader_id=current_user.id,
            make_primary=not animal.photos,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"success": True, "data": {"photo_id": p.id}}


@router.delete("/{livestock_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_photo(
    livestock_id: int,
    photo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN, UserRole.FARM_OWNER):
        raise HTTPException(status_code=403, detail="Forbidden")
    animal = await get_livestock(livestock_id, db)
    if not animal:
        raise HTTPException(status_code=404, detail="Not found")
    await delete_photo(photo_id, animal, db)
