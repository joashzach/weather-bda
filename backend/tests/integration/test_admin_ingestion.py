"""Integration tests for Admin Ingestion API endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.db.models.data_sources import DataSource
from app.db.models.users import User


def test_trigger_ingestion_flow_and_errors(client: TestClient, db_session: Session):
    admin = User(
        email="admin_ingest@example.com",
        display_name="Admin",
        password_hash=hash_password("adminpassword123"),
        role="admin",
        is_active=True,
    )
    unconfigured_source = DataSource(
        name="unconfigured_ingest_source",
        display_name="Unconfigured",
        source_type="rss",
        adapter_key="rss",
        trust_level="news",
        is_enabled=False,
        attribution_text="Test",
        config={},  # Missing feed_url
    )
    configured_source = DataSource(
        name="configured_ingest_source",
        display_name="Configured Open Meteo",
        source_type="weather_api",
        adapter_key="open_meteo",
        trust_level="provider_model",
        is_enabled=True,
        attribution_text="Open Meteo",
        config={"past_days": 2, "forecast_days": 7},
    )
    db_session.add_all([admin, unconfigured_source, configured_source])
    db_session.commit()

    admin_token = create_access_token(
        str(admin.id), role="admin", token_version=admin.token_version
    )

    # 1. 404 unknown source
    res_404 = client.post(
        "/api/v1/admin/ingestion/unknown_source_xyz/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "source_not_found"

    # 2. 409 source_not_configured
    res_cfg = client.post(
        f"/api/v1/admin/ingestion/{unconfigured_source.name}/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_cfg.status_code == 409
    assert res_cfg.json()["error"]["code"] == "source_not_configured"

    # 3. 202 Accepted on valid trigger
    res_202 = client.post(
        f"/api/v1/admin/ingestion/{configured_source.name}/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_202.status_code == 202
    data = res_202.json()
    assert data["status"] == "queued"
    run_id = data["run_id"]

    # 4. 409 already_running if triggered again while queued
    res_conflict = client.post(
        f"/api/v1/admin/ingestion/{configured_source.name}/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_conflict.status_code == 409
    assert res_conflict.json()["error"]["code"] == "already_running"

    # 5. GET /admin/ingestion/runs lists the queued run
    res_list = client.get(
        "/api/v1/admin/ingestion/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"source": configured_source.name},
    )
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert len(list_data["items"]) >= 1
    assert list_data["items"][0]["id"] == run_id
    assert list_data["items"][0]["status"] == "queued"

    # 6. GET /admin/ingestion/runs/{run_id} returns detail
    res_detail = client.get(
        f"/api/v1/admin/ingestion/runs/{run_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["id"] == run_id
    assert detail_data["source_name"] == configured_source.name
