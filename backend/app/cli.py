"""Command line administrative interface: configuration validation and administrator bootstrap."""

import argparse
import getpass
import sys

from pydantic import ValidationError

from app.core.config import Settings
from app.core.enums import UserRole
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.repositories.users import UserRepository


def cmd_check_config(_args: argparse.Namespace) -> int:
    """Validate environment settings without leaking secrets. Return 0 if valid, non-zero on failure."""
    try:
        settings = Settings()
        print("Config check passed successfully.")
        print(f"Environment: {settings.ENVIRONMENT}")
        print(f"Database: {settings.DATABASE_URL.split('@')[-1]}")
        print(f"API Docs: {settings.API_DOCS_ENABLED}")
        return 0
    except ValidationError as e:
        print("Configuration validation failed:", file=sys.stderr)
        for err in e.errors():
            loc = ".".join(str(part) for part in err.get("loc", []))
            msg = err.get("msg", "Invalid configuration")
            print(f" - {loc}: {msg}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1


def cmd_create_admin(args: argparse.Namespace) -> int:
    """Bootstrap an initial administrator account with Argon2id password hashing."""
    email = args.email.strip().lower()
    display_name = args.display_name or email.split("@")[0]

    with SessionLocal() as db:
        user_repo = UserRepository(db)
        admin_count = user_repo.count_by_role(UserRole.ADMIN)

        if admin_count > 0 and not args.allow_additional:
            print(
                "Error: An administrator account already exists. Pass --allow-additional to create another.",
                file=sys.stderr,
            )
            return 1

        existing = user_repo.get_by_email(email)
        if existing:
            print(f"Error: User with email '{email}' already exists.", file=sys.stderr)
            return 1

        # Read password
        if args.password_stdin:
            password = sys.stdin.read().strip()
        else:
            password = getpass.getpass("Enter password for admin (min 12 characters): ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Error: Passwords do not match.", file=sys.stderr)
                return 1

        if len(password) < 12:
            print("Error: Password must be at least 12 characters long.", file=sys.stderr)
            return 1

        hashed = hash_password(password)
        admin = user_repo.create(
            email=email,
            display_name=display_name,
            password_hash=hashed,
            role=UserRole.ADMIN,
        )
        print(f"Administrator successfully created with ID: {admin.id}")
        return 0


def cmd_create_user(args: argparse.Namespace) -> int:
    """Create a user with specified role (e.g. reviewer)."""
    email = args.email.strip().lower()
    role = args.role.strip().lower()
    display_name = args.display_name or email.split("@")[0]

    if role not in (UserRole.ADMIN, UserRole.REVIEWER):
        print(f"Error: Role must be '{UserRole.ADMIN}' or '{UserRole.REVIEWER}'.", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        user_repo = UserRepository(db)
        existing = user_repo.get_by_email(email)
        if existing:
            print(f"Error: User with email '{email}' already exists.", file=sys.stderr)
            return 1

        if args.password_stdin:
            password = sys.stdin.read().strip()
        else:
            password = getpass.getpass(f"Enter password for {role} (min 12 characters): ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Error: Passwords do not match.", file=sys.stderr)
                return 1

        if len(password) < 12:
            print("Error: Password must be at least 12 characters long.", file=sys.stderr)
            return 1

        hashed = hash_password(password)
        user = user_repo.create(
            email=email,
            display_name=display_name,
            password_hash=hashed,
            role=role,
        )
        print(f"User ({role}) successfully created with ID: {user.id}")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Weather BDA Backend CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check-config
    check_cfg = subparsers.add_parser("check-config", help="Validate environment settings")
    check_cfg.set_defaults(func=cmd_check_config)

    # create-admin
    admin_parser = subparsers.add_parser("create-admin", help="Bootstrap initial admin user")
    admin_parser.add_argument("--email", required=True, help="Administrator email address")
    admin_parser.add_argument("--display-name", help="Display name (defaults to email handle)")
    admin_parser.add_argument(
        "--password-stdin", action="store_true", help="Read password from stdin"
    )
    admin_parser.add_argument(
        "--allow-additional", action="store_true", help="Allow additional admins"
    )
    admin_parser.set_defaults(func=cmd_create_admin)

    # create-user
    user_parser = subparsers.add_parser("create-user", help="Create reviewer or user account")
    user_parser.add_argument("--email", required=True, help="User email address")
    user_parser.add_argument(
        "--role", required=True, choices=["admin", "reviewer"], help="User role"
    )
    user_parser.add_argument("--display-name", help="Display name")
    user_parser.add_argument(
        "--password-stdin", action="store_true", help="Read password from stdin"
    )
    user_parser.set_defaults(func=cmd_create_user)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
