"""User repository handling database queries and persistence for users."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.db.models.users import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        return self.db.execute(
            select(User).where(func.lower(User.email) == normalized)
        ).scalar_one_or_none()

    def count_by_role(self, role: UserRole | str) -> int:
        role_val = str(role)
        query = select(func.count()).select_from(User).where(User.role == role_val)
        return self.db.execute(query).scalar_one() or 0

    def create(
        self,
        email: str,
        display_name: str,
        password_hash: str,
        role: UserRole | str,
    ) -> User:
        user = User(
            email=email.strip().lower(),
            display_name=display_name.strip(),
            password_hash=password_hash,
            role=str(role),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def record_failed_login(
        self,
        user: User,
        max_failures: int = 5,
        lockout_minutes: int = 15,
    ) -> None:
        from datetime import UTC, datetime, timedelta

        user.failed_login_count += 1
        if user.failed_login_count >= max_failures:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=lockout_minutes)
        self.db.commit()

    def record_successful_login(self, user: User) -> None:
        from datetime import UTC, datetime

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = datetime.now(UTC)
        self.db.commit()

    def update_password(self, user: User, new_password_hash: str) -> None:
        """Update password hash and increment token_version to invalidate prior JWTs."""
        user.password_hash = new_password_hash
        user.token_version += 1
        self.db.commit()

    def update_password_hash_only(self, user: User, new_password_hash: str) -> None:
        """Update password hash during rehash without bumping token_version."""
        user.password_hash = new_password_hash
        self.db.commit()
