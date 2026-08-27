from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import AppUser
from app.services.breeding import find_breeding_matches

router = APIRouter(prefix="/breeding", tags=["breeding"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/match", response_class=HTMLResponse)
async def breeding_match_form(
    request: Request,
    current_user: AppUser = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "breeding/match.html",
        {"request": request, "current_user": current_user, "results": None, "searched": False},
    )


@router.post("/match", response_class=HTMLResponse)
async def breeding_match_submit(
    request: Request,
    cow_id: Optional[int] = Form(None),
    max_distance_km: Optional[float] = Form(None),
    top_n: int = Form(10),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = current_user.jzd_id or 0
    cross_jzd = current_user.role.is_cross_jzd_reader
    results = await find_breeding_matches(
        jzd_id, db,
        max_distance_km=max_distance_km,
        cow_id=cow_id or None,
        top_n=top_n,
        cross_jzd=cross_jzd,
    )
    return templates.TemplateResponse(
        "breeding/match.html",
        {
            "request": request, "current_user": current_user,
            "results": results, "searched": True,
            "cow_id": cow_id, "max_distance_km": max_distance_km, "top_n": top_n,
        },
    )
