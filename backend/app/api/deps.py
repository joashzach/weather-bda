"""FastAPI dependencies for database sessions, authentication, and request contexts."""

from app.db.models.users import User
from app.db.session import get_db


def get_optional_current_user() -> User | None:
    """Dependency returning the authenticated user if present, or None for anonymous callers.
    In Phase 3, this returns None by default until full auth is wired in Phase 4/5.
    Tests override this dependency to test reviewer and admin role permissions.
    """
    return None


def is_staff(user: User | None) -> bool:
    """Return True if user is a reviewer or admin."""
    return user is not None and user.role in ("reviewer", "admin")


def is_admin(user: User | None) -> bool:
    """Return True if user is an admin."""
    return user is not None and user.role == "admin"


# Re-export get_db for api routers
__all__ = ["get_db", "get_optional_current_user", "is_staff", "is_admin"]
