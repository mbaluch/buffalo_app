from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import AppUser
from app.services.breeding import find_breeding_matches

router = APIRouter(prefix="/api/v1/breeding", tags=["api:breeding"])


@router.get("/match")
async def api_breeding_match(
    cow_id: Optional[int] = Query(None),
    max_distance_km: Optional[float] = Query(None),
    top_n: int = Query(10, ge=1, le=50),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = current_user.jzd_id or 0
    cross_jzd = current_user.role.is_cross_jzd_reader
    results = await find_breeding_matches(
        jzd_id, db,
        max_distance_km=max_distance_km,
        cow_id=cow_id,
        top_n=top_n,
        cross_jzd=cross_jzd,
    )
    return {"results": results, "count": len(results)}
