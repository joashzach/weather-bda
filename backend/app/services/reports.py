"""Citizen reports and moderation review service enforcing business rules, concurrency, and privacy."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import generate_tracking_token, hash_ip, hash_tracking_token
from app.db.models.citizen_reports import CitizenReport
from app.db.models.users import User
from app.repositories.reports import CitizenReportRepository
from app.schemas.common import PaginatedResponse
from app.schemas.locations import LocationPublic
from app.schemas.reports import (
    CitizenReportCreate,
    CitizenReportCreatedResponse,
    CitizenReportPublic,
    CitizenReportStaff,
    EvidencePublic,
    EvidenceStaff,
    ReportReviewDecision,
    ReportReviewItem,
    ReportReviewsResponse,
)
from app.schemas.users import UserPublic

ALLOWED_EVENT_TYPES = {
    "heavy_rain",
    "flood",
    "heatwave",
    "cold_wave",
    "storm",
    "cyclone",
    "drought",
    "landslide",
    "lightning",
    "hail",
    "fog",
    "other",
}

ALLOWED_REPORT_SORTS = {
    "event_time",
    "-event_time",
    "submitted_at",
    "-submitted_at",
}


def _map_evidence_public(evidence_list: list[dict[str, Any]] | None) -> list[EvidencePublic]:
    if not evidence_list:
        return []
    return [
        EvidencePublic(
            type=item.get("type", "other"),
            description=item.get("description", ""),
            has_link=bool(item.get("url")),
        )
        for item in evidence_list
    ]


def _map_evidence_staff(evidence_list: list[dict[str, Any]] | None) -> list[EvidenceStaff]:
    if not evidence_list:
        return []
    return [
        EvidenceStaff(
            type=item.get("type", "other"),
            url=item.get("url", ""),
            description=item.get("description", ""),
            has_link=bool(item.get("url")),
        )
        for item in evidence_list
    ]


def _map_location_public(loc) -> LocationPublic | None:
    if not loc:
        return None
    return LocationPublic(
        id=loc.id,
        slug=loc.slug,
        name=loc.name,
        region=loc.region,
        country_code=loc.country_code,
        latitude=float(loc.latitude),
        longitude=float(loc.longitude),
    )


def _to_public_report(report: CitizenReport) -> CitizenReportPublic:
    return CitizenReportPublic(
        id=report.id,
        event_type=report.event_type or "other",
        severity=report.severity,
        description=report.description or "",
        location_name=report.location_name,
        latitude=float(report.latitude) if report.latitude is not None else 0.0,
        longitude=float(report.longitude) if report.longitude is not None else 0.0,
        location=_map_location_public(report.location),
        event_time=report.event_time or datetime.now(UTC),
        evidence=_map_evidence_public(report.evidence),
        status=report.status,
        submitted_at=report.submitted_at or datetime.now(UTC),
        reviewed_at=report.reviewed_at,
    )


def _to_staff_report(report: CitizenReport) -> CitizenReportStaff:
    reviewer_public = None
    if report.reviewer:
        reviewer_public = UserPublic(
            id=report.reviewer.id,
            email=report.reviewer.email,
            display_name=report.reviewer.display_name,
            role=report.reviewer.role,
        )

    return CitizenReportStaff(
        id=report.id,
        event_type=report.event_type or "other",
        severity=report.severity,
        description=report.description or "",
        location_name=report.location_name,
        latitude=float(report.latitude) if report.latitude is not None else 0.0,
        longitude=float(report.longitude) if report.longitude is not None else 0.0,
        location=_map_location_public(report.location),
        event_time=report.event_time or datetime.now(UTC),
        evidence=_map_evidence_staff(report.evidence),
        status=report.status,
        submitted_at=report.submitted_at or datetime.now(UTC),
        reviewed_at=report.reviewed_at,
        contact_email=report.contact_email,
        row_version=report.row_version,
        reviewed_by=reviewer_public,
    )


class CitizenReportService:
    @staticmethod
    def create_report(
        db: Session,
        body: CitizenReportCreate,
        client_ip: str | None = None,
    ) -> CitizenReportCreatedResponse:
        settings = get_settings()
        repo = CitizenReportRepository(db)

        # 1. Validate event_type
        if body.event_type not in ALLOWED_EVENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"Invalid event_type '{body.event_type}'. Allowed: {sorted(ALLOWED_EVENT_TYPES)}",
                },
            )

        # 2. Validate event_time bounds (not > 5 mins in future, not older than REPORT_MAX_AGE_DAYS)
        now = datetime.now(UTC)
        if body.event_time > now + timedelta(minutes=5):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": "event_time cannot be more than 5 minutes in the future",
                },
            )

        max_age = timedelta(days=settings.REPORT_MAX_AGE_DAYS)
        if body.event_time < now - max_age:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"event_time cannot be older than {settings.REPORT_MAX_AGE_DAYS} days",
                },
            )

        # 3. Abuse control: duplicate submission check
        ip_hash_val = hash_ip(client_ip)
        if repo.check_recent_duplicate(ip_hash_val, body.description, window_hours=1):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "conflict",
                    "message": "Duplicate report submitted recently. Please wait before submitting again.",
                },
            )

        # 4. Nearest location lookup within 50 km
        nearest_loc = repo.find_nearest_location(
            lat=body.latitude,
            lon=body.longitude,
            max_radius_km=settings.REPORT_LOCATION_RADIUS_KM,
        )
        location_id = nearest_loc.id if nearest_loc else None

        # 5. One-time tracking token generation
        tracking_token = generate_tracking_token()
        token_hash = hash_tracking_token(tracking_token)

        # 6. Build model instance
        evidence_dicts = [e.model_dump() for e in body.evidence]
        report = CitizenReport(
            event_type=body.event_type,
            severity=body.severity,
            description=body.description.strip(),
            location_name=body.location_name.strip() if body.location_name else None,
            latitude=body.latitude,
            longitude=body.longitude,
            location_id=location_id,
            event_time=body.event_time,
            evidence=evidence_dicts,
            contact_email=body.contact_email,
            status="pending",
            submitted_at=now,
            reviewed_at=None,
            reviewed_by=None,
            ip_hash=ip_hash_val,
            tracking_token_hash=token_hash,
            row_version=1,
        )

        repo.create(report)

        return CitizenReportCreatedResponse(
            id=report.id,
            status="pending",
            submitted_at=report.submitted_at,
            tracking_token=tracking_token,
        )

    @staticmethod
    def get_report_by_id(
        db: Session,
        report_id: uuid.UUID,
        tracking_token: str | None = None,
        current_user: User | None = None,
    ) -> CitizenReportPublic | CitizenReportStaff:
        repo = CitizenReportRepository(db)
        report = repo.get_by_id(report_id)

        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "not_found", "message": "Report not found"},
            )

        is_staff = current_user is not None and current_user.role in ("reviewer", "admin")
        is_owner = False
        if tracking_token:
            token_hash = hash_tracking_token(tracking_token)
            is_owner = secrets.compare_digest(token_hash, report.tracking_token_hash)

        # Non-verified reports require staff auth or valid tracking token; otherwise 404
        if report.status != "verified" and not is_staff and not is_owner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "not_found", "message": "Report not found"},
            )

        if is_staff:
            return _to_staff_report(report)
        return _to_public_report(report)

    @staticmethod
    def list_reports(
        db: Session,
        current_user: User | None = None,
        status_filter: str | None = None,
        event_type: str | None = None,
        location_id: int | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        sort: str = "-event_time",
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse[Any]:
        repo = CitizenReportRepository(db)

        if sort not in ALLOWED_REPORT_SORTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"Invalid sort parameter '{sort}'. Allowed: {sorted(ALLOWED_REPORT_SORTS)}",
                },
            )

        # Max span check: 31 days for raw record lists per PRD Section 7.1
        if from_time and to_time:
            if from_time >= to_time:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "validation_error",
                        "message": "'from' timestamp must be strictly earlier than 'to' timestamp",
                    },
                )
            if (to_time - from_time).total_seconds() > 31 * 86400:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "validation_error",
                        "message": "Maximum allowed time span for reports list is 31 days",
                    },
                )

        is_staff = current_user is not None and current_user.role in ("reviewer", "admin")

        # Anonymous callers receive verified reports only; status filter is forbidden
        if not is_staff and status_filter and status_filter != "verified":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "forbidden",
                    "message": "Staff credentials required to filter by status",
                },
            )

        effective_status = status_filter if is_staff else "verified"

        items, total = repo.list_reports(
            status_filter=effective_status,
            event_type=event_type,
            location_id=location_id,
            from_time=from_time,
            to_time=to_time,
            sort=sort,
            limit=limit,
            offset=offset,
        )

        mapped_items = [_to_staff_report(r) if is_staff else _to_public_report(r) for r in items]
        return PaginatedResponse(
            items=mapped_items,
            total=total,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def list_pending_reports(
        db: Session,
        event_type: str | None = None,
        location_id: int | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        sort: str = "submitted_at",
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse[CitizenReportStaff]:
        repo = CitizenReportRepository(db)

        items, total = repo.list_pending_reports(
            event_type=event_type,
            location_id=location_id,
            from_time=from_time,
            to_time=to_time,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        return PaginatedResponse(
            items=[_to_staff_report(r) for r in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def review_report(
        db: Session,
        report_id: uuid.UUID,
        body: ReportReviewDecision,
        reviewer: User,
    ) -> CitizenReportStaff:
        repo = CitizenReportRepository(db)

        # 1. Pessimistic lock on report row
        report = repo.get_by_id_for_update(report_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "not_found", "message": "Report not found"},
            )

        # 2. Optimistic locking version check
        if report.row_version != body.expected_row_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "stale_version",
                    "message": f"Report version mismatch. Expected {body.expected_row_version}, found {report.row_version}",
                },
            )

        # 3. State machine transition rules per PRD Section 7.6
        from_status = report.status
        decision = body.decision

        target_status: str
        notes_required: bool
        allowed_roles: set[str]

        if from_status == "pending" and decision == "verify":
            target_status = "verified"
            notes_required = False
            allowed_roles = {"reviewer", "admin"}
        elif from_status == "pending" and decision == "reject":
            target_status = "rejected"
            notes_required = True
            allowed_roles = {"reviewer", "admin"}
        elif from_status == "verified" and decision == "reject":
            # Retraction
            target_status = "rejected"
            notes_required = True
            allowed_roles = {"admin"}
        elif from_status == "rejected" and decision == "reopen":
            # Reopen
            target_status = "pending"
            notes_required = True
            allowed_roles = {"admin"}
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "invalid_transition",
                    "message": f"Cannot execute decision '{decision}' on report with status '{from_status}'",
                },
            )

        # 4. Role validation for transition
        if reviewer.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "forbidden",
                    "message": f"Action '{decision}' on status '{from_status}' requires {allowed_roles} privileges",
                },
            )

        # 5. Notes requirement validation
        if notes_required:
            has_notes = bool(body.notes and body.notes.strip()) or bool(
                body.reason_code and body.reason_code.strip()
            )
            if not has_notes:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "validation_error",
                        "message": "Notes or reason_code is required for this decision",
                    },
                )

        # 6. Execute transition in transaction
        now = datetime.now(UTC)
        report.status = target_status
        report.reviewed_at = None if target_status == "pending" else now
        report.reviewed_by = None if target_status == "pending" else reviewer.id
        report.row_version += 1

        repo.add_review(
            report_id=report.id,
            reviewer_id=reviewer.id,
            from_status=from_status,
            to_status=target_status,
            private_notes=body.notes.strip() if body.notes else None,
            reason_code=body.reason_code.strip() if body.reason_code else None,
            created_at=now,
        )

        repo.add_audit_event(
            actor_user_id=reviewer.id,
            action="report.reviewed",
            entity_type="citizen_report",
            entity_id=str(report.id),
            metadata={
                "from_status": from_status,
                "to_status": target_status,
                "reason_code": body.reason_code,
                "row_version": report.row_version,
            },
            created_at=now,
        )

        db.commit()

        # Reload report with joined relationships for response
        reloaded = repo.get_by_id(report.id)
        return _to_staff_report(reloaded or report)

    @staticmethod
    def list_reviews_for_report(
        db: Session,
        report_id: uuid.UUID,
    ) -> ReportReviewsResponse:
        repo = CitizenReportRepository(db)
        report = repo.get_by_id(report_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "not_found", "message": "Report not found"},
            )

        reviews = repo.list_reviews_for_report(report_id)
        items = [
            ReportReviewItem(
                id=r.id,
                reviewer=UserPublic(
                    id=r.reviewer.id,
                    email=r.reviewer.email,
                    display_name=r.reviewer.display_name,
                    role=r.reviewer.role,
                ),
                from_status=r.from_status,
                to_status=r.to_status,
                reason_code=r.reason_code,
                private_notes=r.private_notes,
                created_at=r.created_at,
            )
            for r in reviews
        ]
        return ReportReviewsResponse(items=items)
