"""Admin API endpoints for manual ingestion triggers and run inspection."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.db.models.users import User
from app.schemas.admin import (
    IngestionRunDetail,
    IngestionRunListResponse,
    IngestionRunTriggerResponse,
)
from app.services.admin import AdminService

router = APIRouter(prefix="/ingestion", tags=["Admin Ingestion"])


@router.post(
    "/{source_name}/run",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestionRunTriggerResponse,
    summary="Trigger a manual ingestion run",
)
def trigger_ingestion(
    source_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> IngestionRunTriggerResponse:
    service = AdminService(db)
    return service.trigger_ingestion(source_name=source_name, actor_user_id=current_user.id)


@router.get(
    "/runs",
    response_model=IngestionRunListResponse,
    summary="List ingestion runs with filters and pagination",
)
def list_ingestion_runs(
    source: str | None = Query(None, description="Filter by source name"),
    run_status: str | None = Query(None, alias="status", description="Filter by run status"),
    from_time: datetime | None = Query(None, alias="from", description="Lower bound for queued_at"),
    to_time: datetime | None = Query(None, alias="to", description="Upper bound for queued_at"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
) -> IngestionRunListResponse:
    service = AdminService(db)
    return service.list_ingestion_runs(
        source=source,
        run_status=run_status,
        from_time=from_time,
        to_time=to_time,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/runs/{run_id}",
    response_model=IngestionRunDetail,
    summary="Get details and sanitized errors for a specific ingestion run",
)
def get_ingestion_run(
    run_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
) -> IngestionRunDetail:
    service = AdminService(db)
    return service.get_ingestion_run(run_id=run_id)
