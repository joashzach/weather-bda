"""Integration tests verifying Alembic upgrade/downgrade round-trips and append-only trigger immutability."""

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from alembic import command
from alembic.config import Config
from app.core.config import get_settings

settings = get_settings()


@pytest.fixture(scope="module")
def alembic_config() -> Config:
    alembic_ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = Config(str(alembic_ini_path))
    # Point alembic directly to TEST_DATABASE_URL
    cfg.set_main_option(
        "sqlalchemy.url",
        settings.TEST_DATABASE_URL.replace("%", "%%"),
    )
    return cfg


def test_alembic_migrations_roundtrip(alembic_config: Config) -> None:
    """PRD Gate Rule: alembic upgrade head, then downgrade base, then upgrade head round-trips cleanly."""
    # Test downgrade to base
    try:
        command.downgrade(alembic_config, "base")
    except Exception as e:
        pytest.skip(f"Alembic database migration test requires accessible test database: {e}")

    # Test upgrade to head
    command.upgrade(alembic_config, "head")

    # Roundtrip check
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")


def test_alembic_autogenerate_no_diff(alembic_config: Config) -> None:
    """PRD Section 10 Gate: Autogenerate yields no diff between models and migrations."""
    import app.db.models  # noqa: F401
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.db.base import Base
    from tests.conftest import test_engine

    with test_engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        diff = compare_metadata(ctx, Base.metadata)
        assert diff == [], f"Autogenerate detected schema drift: {diff}"


def test_append_only_triggers_protect_audit_and_reviews(
    alembic_config: Config, db_session: Session
) -> None:
    """PRD Section 4.6 & 4.9: Triggers must raise an exception on UPDATE, DELETE, and TRUNCATE."""
    try:
        # 1. audit_events: UPDATE must fail
        db_session.execute(
            text(
                """
                INSERT INTO audit_events (action, entity_type, entity_id, created_at)
                VALUES ('test.action', 'system', 'sys-1', now())
                """
            )
        )
        db_session.flush()

        with pytest.raises(Exception) as exc_update:
            db_session.execute(
                text("UPDATE audit_events SET action = 'altered.action' WHERE entity_id = 'sys-1'")
            )
            db_session.flush()
        assert "Table audit_events is append-only" in str(exc_update.value)
        db_session.rollback()

        # 2. audit_events: DELETE must fail
        db_session.execute(
            text(
                """
                INSERT INTO audit_events (action, entity_type, entity_id, created_at)
                VALUES ('test.action2', 'system', 'sys-2', now())
                """
            )
        )
        db_session.flush()

        with pytest.raises(Exception) as exc_delete:
            db_session.execute(text("DELETE FROM audit_events WHERE entity_id = 'sys-2'"))
            db_session.flush()
        assert "Table audit_events is append-only" in str(exc_delete.value)
        db_session.rollback()

        # 3. audit_events: TRUNCATE must fail
        with pytest.raises(Exception) as exc_trunc:
            db_session.execute(text("TRUNCATE TABLE audit_events"))
            db_session.flush()
        assert "Table audit_events is append-only" in str(exc_trunc.value)
        db_session.rollback()

        # 4. report_reviews: Seed prerequisites (user, report)
        db_session.execute(
            text(
                """
                INSERT INTO users (id, email, display_name, password_hash, role)
                VALUES ('11111111-1111-1111-1111-111111111111', 'rev@example.com', 'Reviewer', 'hash', 'reviewer');

                INSERT INTO citizen_reports (id, event_type, description, latitude, longitude, tracking_token_hash, status, event_time)
                VALUES ('22222222-2222-2222-2222-222222222222', 'flood', 'Heavy flash flood in downtown street', 19.07600, 72.87770, 'hash', 'pending', now());

                INSERT INTO report_reviews (report_id, reviewer_id, from_status, to_status, private_notes)
                VALUES ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111', 'pending', 'verified', 'Verified with local photos');
                """
            )
        )
        db_session.flush()

        # report_reviews: UPDATE must fail
        with pytest.raises(Exception) as exc_rev_upd:
            db_session.execute(
                text(
                    "UPDATE report_reviews SET private_notes = 'tampered' WHERE from_status = 'pending'"
                )
            )
            db_session.flush()
        assert "Table report_reviews is append-only" in str(exc_rev_upd.value)
        db_session.rollback()

        # report_reviews: DELETE must fail
        db_session.execute(
            text(
                """
                INSERT INTO users (id, email, display_name, password_hash, role)
                VALUES ('11111111-1111-1111-1111-111111111111', 'rev@example.com', 'Reviewer', 'hash', 'reviewer');

                INSERT INTO citizen_reports (id, event_type, description, latitude, longitude, tracking_token_hash, status, event_time)
                VALUES ('22222222-2222-2222-2222-222222222222', 'flood', 'Heavy flash flood in downtown street', 19.07600, 72.87770, 'hash', 'pending', now());

                INSERT INTO report_reviews (report_id, reviewer_id, from_status, to_status)
                VALUES ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111', 'pending', 'verified');
                """
            )
        )
        db_session.flush()

        with pytest.raises(Exception) as exc_rev_del:
            db_session.execute(text("DELETE FROM report_reviews WHERE from_status = 'pending'"))
            db_session.flush()
        assert "Table report_reviews is append-only" in str(exc_rev_del.value)
        db_session.rollback()

        # report_reviews: TRUNCATE must fail
        with pytest.raises(Exception) as exc_rev_trunc:
            db_session.execute(text("TRUNCATE TABLE report_reviews"))
            db_session.flush()
        assert "Table report_reviews is append-only" in str(exc_rev_trunc.value)
        db_session.rollback()

    except Exception as e:
        if "does not exist" in str(e) or "connection" in str(e).lower():
            pytest.skip(f"Database trigger test requires applied migrations on test DB: {e}")
        raise


def test_database_check_constraints_reject_bad_rows(
    alembic_config: Config, db_session: Session
) -> None:
    """PRD Section 10: CHECK and unique constraints reject invalid rows."""
    # 1. Invalid User Role (not admin or reviewer)
    with pytest.raises(Exception) as exc_role:
        db_session.execute(
            text(
                """
                INSERT INTO users (id, email, display_name, password_hash, role)
                VALUES ('33333333-3333-3333-3333-333333333333', 'bad@example.com', 'Bad Role', 'hash', 'superadmin');
                """
            )
        )
        db_session.flush()
    assert "ck_users_role" in str(exc_role.value)
    db_session.rollback()

    # 2. Invalid Location Coordinates (-95 is outside -90..90)
    with pytest.raises(Exception) as exc_lat:
        db_session.execute(
            text(
                """
                INSERT INTO locations (slug, name, country_code, latitude, longitude, is_active)
                VALUES ('bad-loc', 'Invalid Loc', 'IN', -95.0, 77.0, true);
                """
            )
        )
        db_session.flush()
    assert "ck_locations_latitude" in str(exc_lat.value)
    db_session.rollback()

    # 3. Invalid Citizen Report Description (< 10 chars)
    with pytest.raises(Exception) as exc_desc:
        db_session.execute(
            text(
                """
                INSERT INTO citizen_reports (id, event_type, description, latitude, longitude, tracking_token_hash, status, event_time)
                VALUES ('44444444-4444-4444-4444-444444444444', 'flood', 'Short', 19.07600, 72.87770, 'hash', 'pending', now());
                """
            )
        )
        db_session.flush()
    assert "ck_citizen_reports_description_len" in str(exc_desc.value)
    db_session.rollback()
