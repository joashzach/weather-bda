"""Standardized error envelope handlers conforming to PRD Section 7.1 specifications."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_ctx
from app.schemas.common import ErrorDetail, ErrorResponse

logger = get_logger("app.api.errors")

HTTP_CODE_MAP = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}


def create_error_response(
    status_code: int,
    message: str,
    code: str | None = None,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    req_id = request_id_ctx.get()
    error_code = code or HTTP_CODE_MAP.get(status_code, "error")

    payload = ErrorResponse(
        error=ErrorDetail(
            code=error_code,
            message=message,
            details=details,
            request_id=req_id,
        )
    ).model_dump(exclude_none=True)

    return JSONResponse(status_code=status_code, content=payload, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = None
        details = None
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code")
            message = exc.detail.get("message", "An error occurred")
            details = exc.detail.get("details")
        else:
            message = str(exc.detail)

        return create_error_response(
            status_code=exc.status_code,
            message=message,
            code=code,
            details=details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details: list[dict[str, Any]] = []
        for err in exc.errors():
            loc = err.get("loc", [])
            field = str(loc[-1]) if loc else "body"
            issue = err.get("msg", "Invalid value")
            details.append({"field": field, "issue": issue})

        return create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Request validation failed",
            code="validation_error",
            details=details,
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
        import math
        import time
        from app.core.rate_limit import limiter

        # Report the window that actually rejected this request, including hourly limits.
        current_limit = getattr(_request.state, "view_rate_limit", None)
        retry_after = exc.limit.limit.get_expiry()
        if current_limit is not None:
            reset_at, _remaining = limiter.limiter.get_window_stats(
                current_limit[0], *current_limit[1]
            )
            retry_after = max(1, math.ceil(reset_at - time.time()) + 1)
        headers = {"Retry-After": str(retry_after)}
        return create_error_response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            message="Rate limit exceeded. Please retry after some time.",
            code="rate_limited",
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_server_exception", error=str(exc), exc_info=True)
        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal server error",
            code="internal_error",
        )
