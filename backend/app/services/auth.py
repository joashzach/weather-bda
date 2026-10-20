"""Authentication service enforcing Argon2id verification, anti-enumeration timing defense, and database lockout."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    check_needs_rehash,
    create_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)
from app.db.models.users import User
from app.repositories.users import UserRepository
from app.schemas.auth import MessageResponse, TokenResponse
from app.schemas.users import UserPublic

UNAUTHORIZED_MESSAGE = "Invalid email or password"


class AuthService:
    @staticmethod
    def login(
        db: Session,
        email: str,
        password: str,
        client_ip: str | None = None,
    ) -> TokenResponse:
        settings = get_settings()
        user_repo = UserRepository(db)

        # 1. Anti-enumeration: look up user by email
        user = user_repo.get_by_email(email)
        if user is None:
            # Constant-time dummy verification on nonexistent user
            verify_dummy_password(password)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "unauthorized", "message": UNAUTHORIZED_MESSAGE},
            )

        now = datetime.now(UTC)

        # 2. Check account lockout
        if user.locked_until and user.locked_until > now:
            # Run dummy verification to prevent timing attack that reveals account lockout status
            verify_dummy_password(password)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "unauthorized", "message": UNAUTHORIZED_MESSAGE},
            )

        # 3. Check active status
        if not user.is_active:
            verify_dummy_password(password)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "unauthorized", "message": UNAUTHORIZED_MESSAGE},
            )

        # 4. Verify password with Argon2id
        is_valid = verify_password(password, user.password_hash)
        if not is_valid:
            user_repo.record_failed_login(
                user,
                max_failures=settings.LOGIN_LOCKOUT_THRESHOLD,
                lockout_minutes=settings.LOGIN_LOCKOUT_MINUTES,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "unauthorized", "message": UNAUTHORIZED_MESSAGE},
            )

        # 5. Successful login: reset failed counters and update last_login_at
        user_repo.record_successful_login(user)

        # 6. Rehash if algorithm/cost parameters need upgrade
        if check_needs_rehash(user.password_hash):
            new_hash = hash_password(password)
            user_repo.update_password_hash_only(user, new_hash)

        user_id = user.id if user.id is not None else uuid.uuid4()
        token = create_access_token(
            user_id=user_id,
            role=user.role,
            token_version=user.token_version,
        )
        expires_in = settings.ACCESS_TOKEN_TTL_MINUTES * 60

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=expires_in,
            user=UserPublic(
                id=user_id,
                email=user.email,
                display_name=user.display_name,
                role=user.role,
            ),
        )

    @staticmethod
    def change_password(
        db: Session,
        user: User,
        current_password: str,
        new_password: str,
    ) -> MessageResponse:
        user_repo = UserRepository(db)

        # 1. Verify current password
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "unauthorized", "message": "Current password is incorrect"},
            )

        # 2. Validate new password length >= 12
        if len(new_password) < 12:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": "New password must be at least 12 characters long",
                },
            )

        # 3. Hash new password and increment token_version (revoking all existing tokens)
        new_hash = hash_password(new_password)
        user_repo.update_password(user, new_hash)

        return MessageResponse(message="Password changed successfully. Please log in again.")
