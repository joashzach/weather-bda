"""API v1 router assembly."""

from fastapi import APIRouter

from app.api.v1.admin import admin_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.locations import router as locations_router
from app.api.v1.news import router as news_router
from app.api.v1.reports import router as reports_router
from app.api.v1.weather import router as weather_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(locations_router)
api_v1_router.include_router(weather_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(news_router)
api_v1_router.include_router(admin_router)

__all__ = ["api_v1_router"]
