"""Automated security test matrix verifying OpenAPI authorization gates and schema privacy."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.db.models.users import User
from app.main import app


def test_openapi_admin_routes_rbac_matrix(client: TestClient, db_session: Session):
    """Enumerate every route in the OpenAPI schema and verify that /admin/* routes enforce 401 and 403."""
    reviewer = User(
        email="security_reviewer@example.com",
        display_name="Security Reviewer",
        password_hash=hash_password("password123456"),
        role="reviewer",
        is_active=True,
    )
    db_session.add(reviewer)
    db_session.commit()

    reviewer_token = create_access_token(
        str(reviewer.id), role="reviewer", token_version=reviewer.token_version
    )

    openapi = app.openapi()
    paths = openapi.get("paths", {})

    admin_endpoints = []
    for path, methods in paths.items():
        if "/admin/" in path:
            for method in methods:
                if method.lower() in ("get", "post", "put", "patch", "delete"):
                    admin_endpoints.append((method.upper(), path))

    assert len(admin_endpoints) >= 5, f"Expected admin endpoints, found {len(admin_endpoints)}"

    for method, path in admin_endpoints:
        # Format dummy path params if needed (e.g. {report_id} -> 1, {source_id} -> 1, {source_name} -> 'test')
        test_path = (
            path.replace("{report_id}", "1")
            .replace("{source_id}", "1")
            .replace("{source_name}", "open_meteo")
            .replace("{run_id}", "1")
            .replace("{id}", "1")
        )

        # 1. Anonymous request must be 401
        res_anon = client.request(method, test_path)
        assert (
            res_anon.status_code == 401
        ), f"Expected 401 for anonymous {method} {test_path}, got {res_anon.status_code}"

        # 2. If endpoint is strictly admin-only (not reviewer-accessible like /admin/reports/pending),
        # verify reviewer gets 403
        if not path.startswith("/api/v1/admin/reports"):
            res_rev = client.request(
                method,
                test_path,
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
            assert (
                res_rev.status_code == 403
            ), f"Expected 403 for reviewer {method} {test_path}, got {res_rev.status_code}"


def test_public_schemas_forbid_private_fields():
    """Verify that public schemas do not expose internal/security fields."""
    forbidden_keys = {
        "password_hash",
        "token_version",
        "lockout_until",
        "failed_attempts",
        "tracking_hash",
        "ip_hash",
        "client_ip",
    }

    openapi = app.openapi()
    schemas = openapi.get("components", {}).get("schemas", {})

    public_schemas = [
        name
        for name in schemas
        if any(p in name for p in ("Public", "Weather", "News", "Location"))
    ]

    for schema_name in public_schemas:
        props = schemas[schema_name].get("properties", {})
        for prop in props:
            assert (
                prop not in forbidden_keys
            ), f"Forbidden security field '{prop}' exposed in public schema '{schema_name}'"
