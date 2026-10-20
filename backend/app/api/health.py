"""Health check endpoints for liveness and database/migration readiness."""

from pathlib import Path

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from app.db.session import engine
from app.schemas.health import LivenessResponse, ReadinessResponse

router = APIRouter(tags=["Health"])


@router.get("/health/live", response_model=LivenessResponse, summary="Process liveness check")
def health_live() -> LivenessResponse:
    """Liveness probe indicating process is up and responding. Performs zero I/O."""
    return LivenessResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={
        200: {"model": ReadinessResponse, "description": "System ready to serve traffic"},
        503: {"model": ReadinessResponse, "description": "Database or migrations not ready"},
    },
    summary="Readiness check for database connectivity and migration state",
)
def health_ready(response: Response) -> ReadinessResponse:
    """Readiness probe checking database connectivity (SELECT 1) and Alembic head revision alignment."""
    checks = {
        "database": "fail",
        "migrations": "fail",
    }

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            checks["database"] = "ok"

            alembic_ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
            alembic_cfg = Config(str(alembic_ini_path))
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            expected_head = script_dir.get_current_head()

            migration_context = MigrationContext.configure(connection)
            current_rev = migration_context.get_current_revision()

            if (
                expected_head is not None
                and current_rev == expected_head
                or expected_head is None
                and current_rev is None
            ):
                checks["migrations"] = "ok"
            else:
                checks["migrations"] = "fail"
    except Exception:
        checks["database"] = "fail"
        checks["migrations"] = "fail"

    is_ready = checks["database"] == "ok" and checks["migrations"] == "ok"

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="unavailable", checks=checks)

    return ReadinessResponse(status="ok", checks=checks)
