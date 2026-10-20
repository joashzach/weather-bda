"""Admin moderation endpoints for citizen reports queue, state transitions, and review history."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_reviewer
from app.db.models.users import User
from app.schemas.common import PaginatedResponse
from app.schemas.reports import (
    CitizenReportStaff,
    ReportReviewDecision,
    ReportReviewsResponse,
)
from app.services.reports import CitizenReportService

router = APIRouter(prefix="/reports", tags=["Admin - Moderation"])


@router.get(
    "/pending",
    response_model=PaginatedResponse[CitizenReportStaff],
    summary="List pending reports for moderation queue",
    description="Returns pending citizen reports ordered oldest-first by default for moderation review.",
)
def list_pending_reports(
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
        description="Filter reports submitted_at >= from (UTC ISO 8601)",
    ),
    to_time: datetime | None = Query(
        default=None,
        alias="to",
        description="Filter reports submitted_at <= to (UTC ISO 8601)",
    ),
    sort: str = Query(
        default="submitted_at",
        description="Sort by 'submitted_at', '-submitted_at', 'event_time', '-event_time'",
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
    current_user: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CitizenReportStaff]:
    return CitizenReportService.list_pending_reports(
        db=db,
        event_type=event_type,
        location_id=location_id,
        from_time=from_time,
        to_time=to_time,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{id}/review",
    response_model=CitizenReportStaff,
    summary="Execute moderation transition review on a citizen report",
    description=(
        "Executes a transition on the report (verify, reject, reopen). "
        "Requires optimistic row_version match. Writes immutable review and audit records."
    ),
)
def review_report(
    id: uuid.UUID,
    body: ReportReviewDecision,
    current_user: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> CitizenReportStaff:
    return CitizenReportService.review_report(
        db=db,
        report_id=id,
        body=body,
        reviewer=current_user,
    )


@router.get(
    "/{id}/reviews",
    response_model=ReportReviewsResponse,
    summary="Inspect review history for a citizen report",
    description="Returns the full immutable review audit trail including reviewer identities and private notes.",
)
def list_reviews_for_report(
    id: uuid.UUID,
    current_user: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> ReportReviewsResponse:
    return CitizenReportService.list_reviews_for_report(
        db=db,
        report_id=id,
    )
