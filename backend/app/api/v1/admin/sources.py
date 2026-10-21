from app.schemas.common import paginate_collection
"""Admin API endpoints for managing data sources."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.security import hash_ip
from app.db.models.users import User
from app.schemas.admin import (
    DataSourceAdminItem,
    DataSourceListResponse,
    DataSourceUpdatePayload,
)
from app.services.admin import AdminService

router = APIRouter(prefix="/sources", tags=["Admin Sources"])


@router.get(
    "",
    response_model=DataSourceListResponse,
    summary="List all data sources with configuration status and last run summary",
)
def list_sources(
    limit: int | None = Query(None, ge=1, le=200, description="Optional page size; clients use 50. Omit for the complete legacy response."),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
) -> DataSourceListResponse:
    service = AdminService(db)
    result = service.list_sources()
    return paginate_collection(result, limit, offset)


@router.patch(
    "/{id}",
    response_model=DataSourceAdminItem,
    summary="Update data source configuration, interval, or status",
)
def update_source(
    id: int,
    payload: DataSourceUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DataSourceAdminItem:
    client_ip = request.client.host if request.client else "unknown"
    service = AdminService(db)
    ip_h = hash_ip(client_ip)
    return service.update_source(
        source_id=id,
        payload=payload,
        actor_user_id=current_user.id,
        ip_hash=ip_h,
    )
