"""FastAPI application factory, middleware pipeline, and route wiring."""

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.v1 import api_v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, request_id_ctx, user_id_ctx
from app.core.rate_limit import limiter

settings = get_settings()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context initializing structured logging and background resources."""
    configure_logging(settings.LOG_LEVEL)
    logger.info(
        "server_startup",
        environment=settings.ENVIRONMENT,
        docs_enabled=settings.API_DOCS_ENABLED,
    )
    yield
    logger.info("server_shutdown")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware establishing request_id, security headers, and structured JSON access logs."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()

        # Extract or generate X-Request-ID
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request_id_ctx.set(req_id)
        user_id_ctx.set(None)

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = req_id

        # Security headers (PRD Section 6.7)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"

        # Apply Cache-Control: no-store on sensitive auth/admin paths
        path = request.url.path
        if path.startswith("/api/v1/auth") or path.startswith("/api/v1/admin"):
            response.headers["Cache-Control"] = "no-store"

        logger.info(
            "http_request",
            method=request.method,
            path=path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=req_id,
        )

        return response


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title="Weather Big Data Analytics API",
        version="1.0.0",
        description="REST API for weather observations, forecasts, citizen reports, and analytics.",
        docs_url="/docs" if settings.API_DOCS_ENABLED else None,
        redoc_url="/redoc" if settings.API_DOCS_ENABLED else None,
        openapi_url="/openapi.json" if settings.API_DOCS_ENABLED else None,
        lifespan=lifespan,
    )

    # SlowAPI rate limiting state
    app.state.limiter = limiter

    # Middleware pipeline (Order: Context/Headers -> CORS)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Tracking-Token", "X-Request-ID"],
    )

    # Error envelope exception handlers
    register_error_handlers(app)

    # Health router mounted at root
    app.include_router(health_router)

    # API v1 routes mounted under /api/v1
    app.include_router(api_v1_router)

    return app


app = create_app()
