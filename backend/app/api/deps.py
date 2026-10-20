"""FastAPI dependencies for database sessions, authentication, and request contexts."""

from app.db.session import get_db

# Re-export get_db for api routers
__all__ = ["get_db"]
