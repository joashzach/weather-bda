"""Unit tests for AuthService: Argon2id verification, anti-enumeration timing, lockout, and password rotation."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.db.models.users import User
from app.services.auth import UNAUTHORIZED_MESSAGE, AuthService


def test_login_success():
    mock_db = MagicMock()
    plain_password = "SuperSecurePassword123!"
    password_hash = hash_password(plain_password)

    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        display_name="Admin User",
        password_hash=password_hash,
        role="admin",
        is_active=True,
        token_version=0,
        failed_login_count=0,
        locked_until=None,
    )

    with patch("app.services.auth.UserRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_by_email.return_value = user

        res = AuthService.login(
            db=mock_db,
            email="admin@example.com",
            password=plain_password,
        )

        assert res.access_token is not None
        assert res.token_type == "bearer"
        assert res.user.email == "admin@example.com"
        assert res.user.role == "admin"
        mock_repo.record_successful_login.assert_called_once_with(user)


def test_login_nonexistent_user_anti_enumeration():
    mock_db = MagicMock()

    with patch("app.services.auth.UserRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_by_email.return_value = None

        with patch("app.services.auth.verify_dummy_password") as mock_dummy:
            with pytest.raises(HTTPException) as exc:
                AuthService.login(
                    db=mock_db,
                    email="nonexistent@example.com",
                    password="AnyPassword123!",
                )
            assert exc.value.status_code == 401
            assert exc.value.detail["message"] == UNAUTHORIZED_MESSAGE
            mock_dummy.assert_called_once_with("AnyPassword123!")


def test_login_locked_account_anti_enumeration():
    mock_db = MagicMock()
    future = datetime.now(UTC) + timedelta(minutes=15)
    user = User(
        id=uuid.uuid4(),
        email="locked@example.com",
        display_name="Locked User",
        password_hash=hash_password("RealPassword123!"),
        role="reviewer",
        is_active=True,
        token_version=0,
        failed_login_count=5,
        locked_until=future,
    )

    with patch("app.services.auth.UserRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_by_email.return_value = user

        with patch("app.services.auth.verify_dummy_password") as mock_dummy:
            with pytest.raises(HTTPException) as exc:
                AuthService.login(
                    db=mock_db,
                    email="locked@example.com",
                    password="RealPassword123!",
                )
            assert exc.value.status_code == 401
            assert exc.value.detail["message"] == UNAUTHORIZED_MESSAGE
            mock_dummy.assert_called_once()


def test_login_inactive_user_anti_enumeration():
    mock_db = MagicMock()
    user = User(
        id=uuid.uuid4(),
        email="inactive@example.com",
        display_name="Inactive User",
        password_hash=hash_password("RealPassword123!"),
        role="reviewer",
        is_active=False,
        token_version=0,
        failed_login_count=0,
        locked_until=None,
    )

    with patch("app.services.auth.UserRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_by_email.return_value = user

        with patch("app.services.auth.verify_dummy_password") as mock_dummy:
            with pytest.raises(HTTPException) as exc:
                AuthService.login(
                    db=mock_db,
                    email="inactive@example.com",
                    password="RealPassword123!",
                )
            assert exc.value.status_code == 401
            assert exc.value.detail["message"] == UNAUTHORIZED_MESSAGE
            mock_dummy.assert_called_once()


def test_login_wrong_password_records_failure():
    mock_db = MagicMock()
    user = User(
        id=uuid.uuid4(),
        email="reviewer@example.com",
        display_name="Reviewer User",
        password_hash=hash_password("CorrectPassword123!"),
        role="reviewer",
        is_active=True,
        token_version=0,
        failed_login_count=0,
        locked_until=None,
    )

    with patch("app.services.auth.UserRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_by_email.return_value = user

        with pytest.raises(HTTPException) as exc:
            AuthService.login(
                db=mock_db,
                email="reviewer@example.com",
                password="WrongPassword123!",
            )
        assert exc.value.status_code == 401
        assert exc.value.detail["message"] == UNAUTHORIZED_MESSAGE
        mock_repo.record_failed_login.assert_called_once()


def test_login_rehash_needed():
    mock_db = MagicMock()
    plain_password = "CorrectPassword123!"
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        display_name="Admin User",
        password_hash=hash_password(plain_password),
        role="admin",
        is_active=True,
        token_version=0,
        failed_login_count=0,
        locked_until=None,
    )

    with patch("app.services.auth.UserRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_by_email.return_value = user

        with patch("app.services.auth.check_needs_rehash", return_value=True):
            res = AuthService.login(
                db=mock_db,
                email="admin@example.com",
                password=plain_password,
            )
            assert res.access_token is not None
            mock_repo.update_password_hash_only.assert_called_once()


def test_change_password_success():
    mock_db = MagicMock()
    current_plain = "OldPassword1234!"
    new_plain = "BrandNewSecurePassword2026!"
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        display_name="Admin User",
        password_hash=hash_password(current_plain),
        role="admin",
        is_active=True,
        token_version=0,
    )

    with patch("app.services.auth.UserRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        res = AuthService.change_password(
            db=mock_db,
            user=user,
            current_password=current_plain,
            new_password=new_plain,
        )
        assert "successfully" in res.message.lower()
        mock_repo.update_password.assert_called_once()


def test_change_password_wrong_current_password():
    mock_db = MagicMock()
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        display_name="Admin User",
        password_hash=hash_password("RealPassword1234!"),
        role="admin",
        is_active=True,
        token_version=0,
    )

    with pytest.raises(HTTPException) as exc:
        AuthService.change_password(
            db=mock_db,
            user=user,
            current_password="WrongCurrentPassword!",
            new_password="BrandNewSecurePassword2026!",
        )
    assert exc.value.status_code == 401
    assert "current password is incorrect" in exc.value.detail["message"].lower()


def test_change_password_short_new_password():
    mock_db = MagicMock()
    current_plain = "OldPassword1234!"
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        display_name="Admin User",
        password_hash=hash_password(current_plain),
        role="admin",
        is_active=True,
        token_version=0,
    )

    with pytest.raises(HTTPException) as exc:
        AuthService.change_password(
            db=mock_db,
            user=user,
            current_password=current_plain,
            new_password="short",
        )
    assert exc.value.status_code == 422
    assert "at least 12 characters" in exc.value.detail["message"]
