from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_current_user
from app.models.user import AppUser, UserRole

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if request.cookies.get("access_token"):
        return RedirectResponse("/dashboard")
    return RedirectResponse("/auth/login")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: AppUser = Depends(get_current_user),
):
    if current_user.role == UserRole.SUPER_ADMIN:
        return RedirectResponse("/admin")

    return templates.TemplateResponse(
        "dashboard/index.html",
        {"request": request, "current_user": current_user},
    )
