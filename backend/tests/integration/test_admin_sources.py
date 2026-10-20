"""Integration tests for Admin Sources API endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.db.models.audit_events import AuditEvent
from app.db.models.data_sources import DataSource
from app.db.models.users import User


def test_admin_sources_rbac(client: TestClient, db_session: Session):
    admin = User(
        email="admin_sources@example.com",
        display_name="Admin",
        password_hash=hash_password("adminpassword123"),
        role="admin",
        is_active=True,
    )
    reviewer = User(
        email="reviewer_sources@example.com",
        display_name="Reviewer",
        password_hash=hash_password("reviewerpassword123"),
        role="reviewer",
        is_active=True,
    )
    db_session.add_all([admin, reviewer])
    db_session.commit()

    admin_token = create_access_token(
        str(admin.id), role="admin", token_version=admin.token_version
    )
    reviewer_token = create_access_token(
        str(reviewer.id), role="reviewer", token_version=reviewer.token_version
    )

    # 1. Anonymous -> 401
    res_anon = client.get("/api/v1/admin/sources")
    assert res_anon.status_code == 401

    # 2. Reviewer -> 403
    res_rev = client.get(
        "/api/v1/admin/sources",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert res_rev.status_code == 403

    # 3. Admin -> 200
    res_admin = client.get(
        "/api/v1/admin/sources",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_patch_source_enabling_unconfigured_fails_409(client: TestClient, db_session: Session):
    admin = User(
        email="admin_cfg@example.com",
        display_name="Admin",
        password_hash=hash_password("adminpassword123"),
        role="admin",
        is_active=True,
    )
    src = DataSource(
        name="test_unconfigured_rss",
        display_name="Test RSS",
        source_type="rss",
        adapter_key="rss",
        trust_level="news",
        is_enabled=False,
        attribution_text="Test RSS feed",
        config={},  # Missing feed_url
    )
    db_session.add_all([admin, src])
    db_session.commit()

    admin_token = create_access_token(
        str(admin.id), role="admin", token_version=admin.token_version
    )

    # Attempting to enable unconfigured source must return 409 source_not_configured
    res = client.patch(
        f"/api/v1/admin/sources/{src.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_enabled": True},
    )
    assert res.status_code == 409
    body = res.json()
    assert body["error"]["code"] == "source_not_configured"


def test_patch_source_success_and_auditing(client: TestClient, db_session: Session):
    admin = User(
        email="admin_patch@example.com",
        display_name="Admin",
        password_hash=hash_password("adminpassword123"),
        role="admin",
        is_active=True,
    )
    src = DataSource(
        name="open_meteo_patch_test",
        display_name="Open-Meteo",
        source_type="weather_api",
        adapter_key="open_meteo",
        trust_level="provider_model",
        is_enabled=False,
        interval_seconds=3600,
        attribution_text="Open-Meteo test",
        config={"past_days": 2, "forecast_days": 7},
    )
    db_session.add_all([admin, src])
    db_session.commit()

    admin_token = create_access_token(
        str(admin.id), role="admin", token_version=admin.token_version
    )

    # Update interval_seconds and is_enabled
    res = client.patch(
        f"/api/v1/admin/sources/{src.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "interval_seconds": 1800,
            "is_enabled": True,
            "display_name": "Open-Meteo Updated",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["interval_seconds"] == 1800
    assert data["is_enabled"] is True
    assert data["display_name"] == "Open-Meteo Updated"

    # Verify audit event written
    audit = (
        db_session.query(AuditEvent)
        .filter_by(action="update_source", entity_id=str(src.id))
        .first()
    )
    assert audit is not None
    assert audit.actor_user_id == admin.id
    assert "interval_seconds" in audit.event_metadata["changed_fields"]
    assert "is_enabled" in audit.event_metadata["changed_fields"]
