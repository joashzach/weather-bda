"""Integration tests for Cross-Origin Resource Sharing (CORS) policies."""

from fastapi.testclient import TestClient


def test_cors_allowed_origin_preflight_and_headers(client: TestClient) -> None:
    origin = "http://localhost:5173"

    # Preflight OPTIONS request
    preflight_res = client.options(
        "/api/v1/weather",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization, content-type, x-tracking-token",
        },
    )
    assert preflight_res.status_code == 200
    assert preflight_res.headers.get("access-control-allow-origin") == origin
    allowed_methods = preflight_res.headers.get("access-control-allow-methods", "")
    assert "GET" in allowed_methods
    assert "POST" in allowed_methods
    assert "OPTIONS" in allowed_methods

    # Normal GET with Origin header
    get_res = client.get("/api/v1/locations", headers={"Origin": origin})
    assert get_res.status_code == 200
    assert get_res.headers.get("access-control-allow-origin") == origin
    exposed_headers = get_res.headers.get("access-control-expose-headers", "")
    assert "x-request-id" in exposed_headers.lower()


def test_cors_disallowed_origin_rejected(client: TestClient) -> None:
    origin = "http://unauthorized-domain.attacker.com"

    res = client.get("/api/v1/locations", headers={"Origin": origin})
    assert res.status_code == 200
    # Disallowed origin should NOT receive Access-Control-Allow-Origin header
    assert "access-control-allow-origin" not in res.headers
