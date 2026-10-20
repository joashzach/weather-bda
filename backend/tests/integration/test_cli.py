"""Integration tests for CLI admin bootstrap and configuration verification."""

import argparse
import sys
from io import StringIO

from sqlalchemy.orm import Session

from app.cli import cmd_check_config, cmd_create_admin, cmd_create_user
from app.core.security import verify_password
from app.repositories.users import UserRepository


def test_cli_check_config() -> None:
    args = argparse.Namespace()
    assert cmd_check_config(args) == 0


def test_cli_create_admin_and_prevent_duplicate(db_session: Session, monkeypatch) -> None:
    # Use monkeypatch to redirect sys.stdin for --password-stdin
    monkeypatch.setattr("app.cli.SessionLocal", lambda: db_session)

    # 1. First admin creation
    admin_args = argparse.Namespace(
        email="admin@example.com",
        display_name="Root Admin",
        password_stdin=True,
        allow_additional=False,
    )
    monkeypatch.setattr(sys, "stdin", StringIO("SecurePass12345!\n"))
    assert cmd_create_admin(admin_args) == 0

    repo = UserRepository(db_session)
    admin = repo.get_by_email("admin@example.com")
    assert admin is not None
    assert admin.role == "admin"
    assert verify_password("SecurePass12345!", admin.password_hash) is True

    # 2. Second admin without --allow-additional must fail
    second_admin_args = argparse.Namespace(
        email="second_admin@example.com",
        display_name="Second Admin",
        password_stdin=True,
        allow_additional=False,
    )
    monkeypatch.setattr(sys, "stdin", StringIO("AnotherSecurePass123!\n"))
    assert cmd_create_admin(second_admin_args) == 1

    # 3. Second admin with --allow-additional succeeds
    second_admin_args.allow_additional = True
    monkeypatch.setattr(sys, "stdin", StringIO("AnotherSecurePass123!\n"))
    assert cmd_create_admin(second_admin_args) == 0


def test_cli_create_reviewer_user(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.cli.SessionLocal", lambda: db_session)

    reviewer_args = argparse.Namespace(
        email="moderator@example.com",
        role="reviewer",
        display_name="Moderator One",
        password_stdin=True,
    )
    monkeypatch.setattr(sys, "stdin", StringIO("ReviewerSecretKey123!\n"))
    assert cmd_create_user(reviewer_args) == 0

    repo = UserRepository(db_session)
    user = repo.get_by_email("moderator@example.com")
    assert user is not None
    assert user.role == "reviewer"
    assert verify_password("ReviewerSecretKey123!", user.password_hash) is True

    # Test get_by_id
    user_by_id = repo.get_by_id(user.id)
    assert user_by_id is not None
    assert user_by_id.email == "moderator@example.com"


def test_cli_create_admin_validations(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.cli.SessionLocal", lambda: db_session)
    repo = UserRepository(db_session)
    repo.create(
        email="existing@example.com",
        display_name="Existing User",
        password_hash="dummy_hash",
        role="admin",
    )

    # 1. Short password (< 12 chars)
    short_pass_args = argparse.Namespace(
        email="short@example.com",
        display_name="Short",
        password_stdin=True,
        allow_additional=True,
    )
    monkeypatch.setattr(sys, "stdin", StringIO("short\n"))
    assert cmd_create_admin(short_pass_args) == 1

    # 2. Existing email
    existing_args = argparse.Namespace(
        email="existing@example.com",
        display_name="Duplicate",
        password_stdin=True,
        allow_additional=True,
    )
    monkeypatch.setattr(sys, "stdin", StringIO("ValidLongPassword123!\n"))
    assert cmd_create_admin(existing_args) == 1

    # 3. getpass mismatch
    import getpass

    mismatch_args = argparse.Namespace(
        email="mismatch@example.com",
        display_name="Mismatch",
        password_stdin=False,
        allow_additional=True,
    )
    passwords = iter(["PasswordOne123!", "PasswordTwo456!"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt: next(passwords))
    assert cmd_create_admin(mismatch_args) == 1


def test_cli_create_user_validations(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.cli.SessionLocal", lambda: db_session)
    repo = UserRepository(db_session)
    repo.create(
        email="existing_user@example.com",
        display_name="Existing User",
        password_hash="dummy_hash",
        role="reviewer",
    )

    # 1. Invalid role
    invalid_role_args = argparse.Namespace(
        email="hacker@example.com",
        role="superuser",
        display_name="Bad Role",
        password_stdin=True,
    )
    monkeypatch.setattr(sys, "stdin", StringIO("ValidLongPassword123!\n"))
    assert cmd_create_user(invalid_role_args) == 1

    # 2. Existing email
    existing_args = argparse.Namespace(
        email="existing_user@example.com",
        role="reviewer",
        display_name="Duplicate",
        password_stdin=True,
    )
    monkeypatch.setattr(sys, "stdin", StringIO("ValidLongPassword123!\n"))
    assert cmd_create_user(existing_args) == 1

    # 3. Short password
    short_pass_args = argparse.Namespace(
        email="short_reviewer@example.com",
        role="reviewer",
        display_name="Short",
        password_stdin=True,
    )
    monkeypatch.setattr(sys, "stdin", StringIO("short\n"))
    assert cmd_create_user(short_pass_args) == 1

    # 4. getpass mismatch
    import getpass

    mismatch_args = argparse.Namespace(
        email="mismatch_rev@example.com",
        role="reviewer",
        display_name="Mismatch",
        password_stdin=False,
    )
    passwords = iter(["PasswordOne123!", "PasswordTwo456!"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt: next(passwords))
    assert cmd_create_user(mismatch_args) == 1


def test_cli_check_config_failure(monkeypatch) -> None:
    from pydantic import ValidationError

    def mock_invalid_settings():
        raise ValidationError.from_exception_data("Settings", [])

    monkeypatch.setattr("app.cli.Settings", mock_invalid_settings)
    args = argparse.Namespace()
    assert cmd_check_config(args) == 1


def test_cli_parser_and_main(monkeypatch) -> None:
    from app.cli import build_parser, main

    parser = build_parser()
    parsed = parser.parse_args(["check-config"])
    assert parsed.command == "check-config"

    # Test main with sys.argv
    monkeypatch.setattr(sys, "argv", ["cli.py", "check-config"])
    exit_codes = []
    monkeypatch.setattr(sys, "exit", lambda code: exit_codes.append(code))
    main()
    assert exit_codes == [0]
