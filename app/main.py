from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.middleware.jzd_context import JzdContextMiddleware
from app.routers import admin, appointments, auth, breeding, dashboard, farms, health_records, importexport, inseminations, livestock
from app.routers.api import livestock as api_livestock
from app.routers.api import breeding as api_breeding

app = FastAPI(
    title="Búvoli — Livestock Management",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(JzdContextMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(farms.router)
app.include_router(livestock.router)
app.include_router(appointments.router)
app.include_router(inseminations.router)
app.include_router(health_records.router)
app.include_router(breeding.router)
app.include_router(importexport.router)
app.include_router(api_livestock.router)
app.include_router(api_breeding.router)
