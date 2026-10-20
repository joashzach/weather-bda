"""Public citizen report endpoints for submission, querying, and single report tracking."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_optional_current_user
from app.core.config import get_settings
from app.core.rate_limit import get_client_ip, limiter
from app.db.models.users import User
from app.schemas.common import PaginatedResponse
from app.schemas.reports import (
    CitizenReportCreate,
    CitizenReportCreatedResponse,
    CitizenReportPublic,
    CitizenReportStaff,
)
from app.services.reports import CitizenReportService

settings = get_settings()
router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post(
    "",
    response_model=CitizenReportCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a citizen weather observation report",
    description=(
        "Submits a public weather report. Automatically assigns proximity location, "
        "hashes client IP, and returns a single-use tracking token."
    ),
)
@limiter.limit(settings.RATE_LIMIT_REPORT_SUBMIT)
def submit_report(
    request: Request,
    body: CitizenReportCreate,
    db: Session = Depends(get_db),
) -> CitizenReportCreatedResponse:
    client_ip = get_client_ip(request)
    return CitizenReportService.create_report(
        db=db,
        body=body,
        client_ip=client_ip,
    )


@router.get(
    "",
    response_model=PaginatedResponse[Any],
    summary="List citizen reports",
    description=(
        "Lists reports. Anonymous users receive verified reports only. "
        "Staff callers (reviewer or admin) can filter across all statuses."
    ),
)
def list_reports(
    status: str | None = Query(
        default=None,
        description="Filter by report status ('pending', 'verified', 'rejected', 'all'). Requires staff role.",
    ),
    event_type: str | None = Query(
        default=None,
        description="Filter by event type",
    ),
    location_id: int | None = Query(
        default=None,
        description="Filter by associated location ID",
    ),
    from_time: datetime | None = Query(
        default=None,
        alias="from",
        description="Filter reports with event_time >= from (UTC ISO 8601)",
    ),
    to_time: datetime | None = Query(
        default=None,
        alias="to",
        description="Filter reports with event_time <= to (UTC ISO 8601)",
    ),
    sort: str = Query(
        default="-event_time",
        description="Sort by 'event_time', '-event_time', 'submitted_at', '-submitted_at'",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Page limit (default 50, maximum 200)",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Page offset (default 0)",
    ),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[Any]:
    return CitizenReportService.list_reports(
        db=db,
        current_user=current_user,
        status_filter=status,
        event_type=event_type,
        location_id=location_id,
        from_time=from_time,
        to_time=to_time,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{id}",
    response_model=CitizenReportPublic | CitizenReportStaff,
    summary="Retrieve a single citizen report by ID",
    description=(
        "Retrieves a report by UUID. Verified reports are visible to all. "
        "Unverified (pending or rejected) reports require staff authentication "
        "or a matching X-Tracking-Token header; returns 404 otherwise."
    ),
)
def get_report(
    id: uuid.UUID,
    x_tracking_token: str | None = Header(
        default=None,
        alias="X-Tracking-Token",
        description="Single-use secret tracking token returned upon report creation",
    ),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> CitizenReportPublic | CitizenReportStaff:
    return CitizenReportService.get_report_by_id(
        db=db,
        report_id=id,
        tracking_token=x_tracking_token,
        current_user=current_user,
    )
