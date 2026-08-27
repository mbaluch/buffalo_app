from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import AppUser
from app.services.auth import (
    authenticate_user,
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
    set_auth_cookies,
)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.cookies.get("access_token"):
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("auth/login.html", {"request": request, "error": None})


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(username, password, db)
    if not user:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    access_token = create_access_token(user)
    refresh_token = await create_refresh_token(user, db)

    redirect_url = "/admin" if user.role.value == "SUPER_ADMIN" else "/dashboard"
    response = RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)
    set_auth_cookies(response, access_token, refresh_token)
    return response


@router.post("/refresh")
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        return RedirectResponse("/auth/login", status_code=status.HTTP_302_FOUND)

    result = await rotate_refresh_token(raw_refresh, db)
    if not result:
        response = RedirectResponse("/auth/login", status_code=status.HTTP_302_FOUND)
        clear_auth_cookies(response)
        return response

    user, new_refresh = result
    new_access = create_access_token(user)
    response = RedirectResponse(request.headers.get("referer", "/dashboard"),
                                status_code=status.HTTP_302_FOUND)
    set_auth_cookies(response, new_access, new_refresh)
    return response


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        await revoke_refresh_token(raw_refresh, db)

    response = RedirectResponse("/auth/login", status_code=status.HTTP_302_FOUND)
    clear_auth_cookies(response)
    return response
