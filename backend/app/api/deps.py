"""FastAPI dependencies for database sessions, authentication, and role-based access control."""

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.logging import user_id_ctx
from app.core.security import decode_access_token
from app.db.models.users import User
from app.db.session import get_db
from app.repositories.users import UserRepository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


def _authenticate_token(token: str, db: Session) -> User:
    """Helper decoding and verifying token validity, user existence, active status, and token_version."""
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid or expired token"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Token missing subject claim"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(str(sub))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid user identity in token"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = UserRepository(db).get_by_id(user_uuid)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "User inactive or not found"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Token version validation (supports instantaneous revocation)
    token_tv = payload.get("tv")
    if token_tv is None or token_tv != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Token has been revoked"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Bind user ID to request context for structured logging
    user_id_ctx.set(str(user.id))
    return user


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Strict authentication dependency: requires valid Bearer access token."""
    if not isinstance(token, str) or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _authenticate_token(token, db)


def get_optional_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Optional authentication dependency: returns User if valid Bearer token provided, None for anonymous."""
    if not isinstance(token, str) or not token:
        return None
    return _authenticate_token(token, db)


def require_role(allowed_roles: str | list[str] | tuple[str, ...]) -> Callable[..., User]:
    """Factory creating an authorization dependency enforcing specific roles."""
    roles = [allowed_roles] if isinstance(allowed_roles, str) else list(allowed_roles)

    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "forbidden",
                    "message": "Insufficient permissions for this resource",
                },
            )
        return user

    return role_checker


# Convenient pre-configured role dependencies
require_reviewer = require_role(["reviewer", "admin"])
require_admin = require_role(["admin"])


def is_staff(user: User | None) -> bool:
    """Return True if user is a reviewer or admin."""
    return user is not None and user.role in ("reviewer", "admin")


def is_admin(user: User | None) -> bool:
    """Return True if user is an admin."""
    return user is not None and user.role == "admin"


__all__ = [
    "get_current_user",
    "get_db",
    "get_optional_current_user",
    "is_admin",
    "is_staff",
    "oauth2_scheme",
    "require_admin",
    "require_reviewer",
    "require_role",
]
