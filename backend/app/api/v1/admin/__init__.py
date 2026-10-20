"""Admin API router assembling all moderation and administration routes."""

from fastapi import APIRouter

from app.api.v1.admin.reports import router as admin_reports_router

admin_router = APIRouter(prefix="/admin")
admin_router.include_router(admin_reports_router)

__all__ = ["admin_router"]
