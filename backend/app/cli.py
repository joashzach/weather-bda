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


def cmd_seed_sources(_args: argparse.Namespace) -> int:
    """Idempotently seed reference data_sources records per PRD Section 4.2."""
    from app.repositories.sources import DataSourceRepository

    sources_to_seed = [
        {
            "name": "open_meteo",
            "display_name": "Open-Meteo Weather Forecast API",
            "source_type": "weather_api",
            "adapter_key": "open_meteo",
            "trust_level": "provider_model",
            "is_enabled": False,
            "interval_seconds": 3600,
            "attribution_text": "Weather data by Open-Meteo.com under CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "homepage_url": "https://open-meteo.com/",
            "config": {"past_days": 2, "forecast_days": 7},
        },
        {
            "name": "citizen_reports",
            "display_name": "Citizen Reports Platform",
            "source_type": "citizen",
            "adapter_key": "citizen",
            "trust_level": "citizen",
            "is_enabled": True,
            "interval_seconds": 3600,
            "attribution_text": "Citizen weather reports",
            "license_url": None,
            "homepage_url": None,
            "config": {},
        },
    ]

    with SessionLocal() as db:
        repo = DataSourceRepository(db)
        for s in sources_to_seed:
            source = repo.upsert(**s)
            print(f"Seeded source: '{source.name}' (ID: {source.id}, enabled: {source.is_enabled})")
        db.commit()

    print("Data sources seeded successfully.")
    return 0


def cmd_seed_locations(args: argparse.Namespace) -> int:
    """Idempotently seed locations from YAML configuration file per PRD Section 4.3."""
    from pathlib import Path

    import yaml

    from app.repositories.locations import LocationRepository

    file_path = Path(args.file)
    if not file_path.is_file():
        print(f"Error: Locations file not found at '{file_path}'.", file=sys.stderr)
        return 1

    try:
        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error reading YAML file: {e}", file=sys.stderr)
        return 1

    locations_data = data.get("locations", [])
    if not locations_data:
        print(f"Warning: No locations found in '{file_path}'.", file=sys.stderr)
        return 0

    with SessionLocal() as db:
        repo = LocationRepository(db)
        for loc in locations_data:
            upserted = repo.upsert(
                slug=loc["slug"],
                name=loc["name"],
                region=loc.get("region"),
                country_code=loc.get("country_code", "IN"),
                latitude=float(loc["latitude"]),
                longitude=float(loc["longitude"]),
                is_active=loc.get("is_active", True),
            )
            print(f"Seeded location: '{upserted.slug}' ({upserted.name}) - ID: {upserted.id}")
        db.commit()

    print(f"Successfully seeded {len(locations_data)} location(s).")
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

    # seed-sources
    sources_parser = subparsers.add_parser(
        "seed-sources", help="Seed default reference data sources"
    )
    sources_parser.set_defaults(func=cmd_seed_sources)

    # seed-locations
    loc_parser = subparsers.add_parser("seed-locations", help="Seed locations from YAML file")
    loc_parser.add_argument(
        "--file", default="config/locations.yaml", help="Path to locations YAML configuration file"
    )
    loc_parser.set_defaults(func=cmd_seed_locations)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
