"""Authentication API endpoints for login, profile inspection, and password rotation."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.rate_limit import get_client_ip, limiter
from app.db.models.users import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, MessageResponse, TokenResponse
from app.schemas.users import UserPublic
from app.services.auth import AuthService

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain JWT access token",
    description="Authenticates credentials with Argon2id and returns a short-lived HS256 JWT access token.",
)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    client_ip = get_client_ip(request)
    return AuthService.login(
        db=db,
        email=body.email,
        password=body.password,
        client_ip=client_ip,
    )


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Current authenticated user profile",
    description="Returns identity, email, display name, and role of the currently authenticated caller.",
)
def get_current_user_profile(
    user: User = Depends(get_current_user),
) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change account password and revoke existing tokens",
    description="Verifies current password, sets new password, and increments token version to revoke earlier tokens.",
)
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    return AuthService.change_password(
        db=db,
        user=user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
