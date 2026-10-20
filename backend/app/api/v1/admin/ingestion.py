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
    "/{source}/run",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestionRunTriggerResponse,
    summary="Trigger a manual ingestion run",
)
def trigger_ingestion(
    source: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> IngestionRunTriggerResponse:
    service = AdminService(db)
    return service.trigger_ingestion(source_name=source, actor_user_id=current_user.id)


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
    limit: int = Query(50, ge=1, le=100, description="Page limit (default 50)"),
    offset: int = Query(0, ge=0, description="Page offset (default 0)"),
    page: int | None = Query(None, ge=1, description="Legacy page number"),
    page_size: int | None = Query(None, ge=1, le=100, description="Legacy page size"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
) -> IngestionRunListResponse:
    service = AdminService(db)
    eff_limit = page_size if page_size is not None else limit
    eff_offset = (page - 1) * eff_limit if page is not None else offset
    return service.list_ingestion_runs(
        source=source,
        run_status=run_status,
        from_time=from_time,
        to_time=to_time,
        limit=eff_limit,
        offset=eff_offset,
    )


@router.get(
    "/runs/{id}",
    response_model=IngestionRunDetail,
    summary="Get details and sanitized errors for a specific ingestion run",
)
def get_ingestion_run(
    id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
) -> IngestionRunDetail:
    service = AdminService(db)
    return service.get_ingestion_run(run_id=id)
