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
