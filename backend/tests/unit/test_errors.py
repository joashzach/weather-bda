"""Unit tests for standard error envelopes and exception handling."""

from fastapi.testclient import TestClient

from app.api.errors import create_error_response
from app.main import app


def test_create_error_response_structure() -> None:
    response = create_error_response(
        status_code=400,
        message="Bad request parameters",
        code="bad_request",
        details=[{"field": "query", "issue": "missing"}],
    )
    assert response.status_code == 400
    data = response.body.decode("utf-8")
    assert '"code":"bad_request"' in data
    assert '"message":"Bad request parameters"' in data
    assert '"field":"query"' in data


def test_validation_error_envelope() -> None:
    # Trigger a 404 or 422 on a test route
    with TestClient(app) as test_client:
        response = test_client.get("/nonexistent-route-for-testing")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "not_found"
        assert "request_id" in data["error"]


def test_custom_http_exception_with_dict_detail() -> None:
    from fastapi import APIRouter
    from starlette.exceptions import HTTPException

    router = APIRouter()

    @router.get("/test-custom-error")
    def trigger_error():
        raise HTTPException(
            status_code=409,
            detail={
                "code": "custom_conflict",
                "message": "Conflict occurred",
                "details": [{"field": "test", "issue": "dup"}],
            },
        )

    app.include_router(router)
    with TestClient(app) as test_client:
        res = test_client.get("/test-custom-error")
        assert res.status_code == 409
        data = res.json()
        assert data["error"]["code"] == "custom_conflict"
        assert data["error"]["message"] == "Conflict occurred"
        assert data["error"]["details"][0]["field"] == "test"


def test_unhandled_exception_returns_500_without_stack_trace() -> None:
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/test-crash")
    def trigger_crash():
        raise RuntimeError("Secret DB password or internal crash trace that must not leak")

    app.include_router(router)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        res = test_client.get("/test-crash")
        assert res.status_code == 500
        data = res.json()
        assert data["error"]["code"] == "internal_error"
        assert data["error"]["message"] == "Internal server error"
        assert "Secret DB password" not in res.text
        assert "request_id" in data["error"]


def test_rate_limit_exceeded_envelope() -> None:
    import asyncio
    from unittest.mock import MagicMock

    from fastapi import Request
    from slowapi.errors import RateLimitExceeded

    dummy_app = app
    handler = dummy_app.exception_handlers[RateLimitExceeded]
    mock_limit = MagicMock()
    mock_limit.error_message = None
    res = asyncio.run(handler(Request({"type": "http"}), RateLimitExceeded(mock_limit)))
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_validation_error_handler_details() -> None:
    from fastapi import APIRouter
    from pydantic import BaseModel

    router = APIRouter()

    class StrictModel(BaseModel):
        count: int

    @router.post("/test-validation")
    def trigger_val(payload: StrictModel):
        return {"count": payload.count}

    app.include_router(router)
    with TestClient(app) as test_client:
        res = test_client.post("/test-validation", json={"count": "not-an-int"})
        assert res.status_code == 422
        data = res.json()
        assert data["error"]["code"] == "validation_error"
        assert len(data["error"]["details"]) > 0
