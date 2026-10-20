"""API layer routers and error handling registration."""

from app.api.health import router as health_router

__all__ = ["health_router"]
