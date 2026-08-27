from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import AppUser, UserRole
from app.services.importexport import (
    export_livestock_csv,
    export_livestock_excel,
    get_import_template_excel,
    import_livestock_csv,
    import_livestock_excel,
)

router = APIRouter(prefix="/import-export", tags=["import-export"])
templates = Jinja2Templates(directory="app/templates")

_ALLOWED_IMPORT_ROLES = {UserRole.SUPER_ADMIN, UserRole.JZD_ADMIN}


@router.get("", response_class=HTMLResponse)
async def ie_dashboard(
    request: Request,
    current_user: AppUser = Depends(get_current_user),
):
    return templates.TemplateResponse(
        "importexport/dashboard.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/template.xlsx")
async def download_template(
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await get_import_template_excel(db)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=livestock_import_template.xlsx"},
    )


@router.get("/export/csv")
async def export_csv(
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = current_user.jzd_id or 0
    data = await export_livestock_csv(db, jzd_id)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=livestock_export.csv"},
    )


@router.get("/export/excel")
async def export_excel(
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jzd_id = current_user.jzd_id or 0
    data = await export_livestock_excel(db, jzd_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=livestock_export.xlsx"},
    )


@router.post("/import", response_class=HTMLResponse)
async def import_livestock(
    request: Request,
    file: UploadFile = File(...),
    preview: str = Form("0"),
    current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in _ALLOWED_IMPORT_ROLES:
        return templates.TemplateResponse(
            "importexport/dashboard.html",
            {"request": request, "current_user": current_user,
             "error": "Insufficient permissions to import"},
        )

    jzd_id = current_user.jzd_id or 0
    content = await file.read()
    is_preview = preview == "1"
    filename = (file.filename or "").lower()

    if filename.endswith(".xlsx"):
        result = await import_livestock_excel(content, db, jzd_id, preview=is_preview)
    else:
        result = await import_livestock_csv(content, db, jzd_id, preview=is_preview)

    return templates.TemplateResponse(
        "importexport/result.html",
        {
            "request": request, "current_user": current_user,
            "result": result, "is_preview": is_preview, "filename": file.filename,
        },
    )
