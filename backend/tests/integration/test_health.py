"""Integration tests for health liveness and readiness endpoints."""

from unittest.mock import MagicMock

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


def test_health_live_endpoint() -> None:
    with TestClient(app) as test_client:
        response = test_client.get("/health/live")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}
        # Asserts security headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Request-ID" in response.headers


def test_health_ready_endpoint_database_failure(monkeypatch) -> None:
    # Simulate database connection failure in health check
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = RuntimeError("Database connection down")
    monkeypatch.setattr("app.api.health.engine", mock_engine)

    with TestClient(app) as test_client:
        response = test_client.get("/health/ready")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "unavailable"
        assert data["checks"]["database"] == "fail"
        # PRD Section 7.2 Rule: No error text leaked in response
        assert "Database connection down" not in response.text


def test_health_ready_endpoint_success(monkeypatch) -> None:
    from tests.conftest import test_engine

    monkeypatch.setattr("app.api.health.engine", test_engine)
    with TestClient(app) as test_client:
        response = test_client.get("/health/ready")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["migrations"] == "ok"


def test_health_ready_endpoint_migration_mismatch(monkeypatch) -> None:
    from alembic.script import ScriptDirectory

    mock_script_dir = MagicMock(spec=ScriptDirectory)
    mock_script_dir.get_current_head.return_value = "unapplied_head_revision"
    monkeypatch.setattr(ScriptDirectory, "from_config", lambda cfg: mock_script_dir)

    with TestClient(app) as test_client:
        response = test_client.get("/health/ready")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "unavailable"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["migrations"] == "fail"


def test_sensitive_paths_cache_control_headers() -> None:
    with TestClient(app) as test_client:
        auth_res = test_client.get("/api/v1/auth/nonexistent")
        assert auth_res.headers.get("Cache-Control") == "no-store"

        admin_res = test_client.get("/api/v1/admin/nonexistent")
        assert admin_res.headers.get("Cache-Control") == "no-store"
