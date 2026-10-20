"""API v1 router assembly."""

from fastapi import APIRouter

from app.api.v1.locations import router as locations_router
from app.api.v1.weather import router as weather_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(locations_router)
api_v1_router.include_router(weather_router)

__all__ = ["api_v1_router"]
