"""Citizen reports and moderation review repository handling database queries and persistence."""

import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models.audit_events import AuditEvent
from app.db.models.citizen_reports import CitizenReport
from app.db.models.locations import Location
from app.db.models.report_reviews import ReportReview


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth using Haversine formula."""
    r = 6371.0  # Earth's mean radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


class CitizenReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_nearest_location(
        self,
        lat: float,
        lon: float,
        max_radius_km: float = 50.0,
    ) -> Location | None:
        """Find the nearest active location within max_radius_km using Haversine formula."""
        active_locations = (
            self.db.execute(select(Location).where(Location.is_active.is_(True))).scalars().all()
        )

        nearest_loc: Location | None = None
        min_dist = float("inf")

        for loc in active_locations:
            dist = haversine_distance_km(lat, lon, float(loc.latitude), float(loc.longitude))
            if dist < min_dist:
                min_dist = dist
                nearest_loc = loc

        if min_dist <= max_radius_km:
            return nearest_loc
        return None

    def check_recent_duplicate(
        self,
        ip_hash: str | None,
        description: str,
        window_hours: int = 1,
    ) -> bool:
        """Check if an identical report from the same IP was submitted within the recent window."""
        if not ip_hash:
            return False

        cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
        query = (
            select(CitizenReport.id)
            .where(
                CitizenReport.ip_hash == ip_hash,
                CitizenReport.description == description.strip(),
                CitizenReport.submitted_at >= cutoff,
            )
            .limit(1)
        )

        result = self.db.execute(query).scalar_one_or_none()
        return result is not None

    def get_by_id(self, report_id: uuid.UUID) -> CitizenReport | None:
        """Fetch citizen report by UUID with eager-loaded relationships."""
        return self.db.execute(
            select(CitizenReport)
            .options(joinedload(CitizenReport.location), joinedload(CitizenReport.reviewer))
            .where(CitizenReport.id == report_id)
        ).scalar_one_or_none()

    def get_by_id_for_update(self, report_id: uuid.UUID) -> CitizenReport | None:
        """Pessimistically lock citizen report row with SELECT FOR UPDATE."""
        return self.db.execute(
            select(CitizenReport).where(CitizenReport.id == report_id).with_for_update()
        ).scalar_one_or_none()

    def create(self, report: CitizenReport) -> CitizenReport:
        """Persist a new citizen report."""
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def list_reports(
        self,
        status_filter: str | None = None,
        event_type: str | None = None,
        location_id: int | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        sort: str = "-event_time",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CitizenReport], int]:
        """Query paginated reports with filtering and deterministic ordering."""
        query = select(CitizenReport).options(
            joinedload(CitizenReport.location),
            joinedload(CitizenReport.reviewer),
        )
        count_query = select(func.count()).select_from(CitizenReport)

        if status_filter and status_filter != "all":
            query = query.where(CitizenReport.status == status_filter)
            count_query = count_query.where(CitizenReport.status == status_filter)

        if event_type:
            query = query.where(CitizenReport.event_type == event_type)
            count_query = count_query.where(CitizenReport.event_type == event_type)

        if location_id is not None:
            query = query.where(CitizenReport.location_id == location_id)
            count_query = count_query.where(CitizenReport.location_id == location_id)

        if from_time:
            query = query.where(CitizenReport.event_time >= from_time)
            count_query = count_query.where(CitizenReport.event_time >= from_time)

        if to_time:
            query = query.where(CitizenReport.event_time < to_time)
            count_query = count_query.where(CitizenReport.event_time < to_time)

        total = self.db.execute(count_query).scalar_one() or 0

        # Sort mapping
        if sort == "event_time":
            query = query.order_by(CitizenReport.event_time.asc(), CitizenReport.id.asc())
        elif sort == "-event_time":
            query = query.order_by(CitizenReport.event_time.desc(), CitizenReport.id.desc())
        elif sort == "submitted_at":
            query = query.order_by(CitizenReport.submitted_at.asc(), CitizenReport.id.asc())
        elif sort == "-submitted_at":
            query = query.order_by(CitizenReport.submitted_at.desc(), CitizenReport.id.desc())
        else:
            query = query.order_by(CitizenReport.event_time.desc(), CitizenReport.id.desc())

        items = self.db.execute(query.limit(limit).offset(offset)).scalars().all()
        return list(items), total

    def list_pending_reports(
        self,
        event_type: str | None = None,
        location_id: int | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        sort: str = "submitted_at",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CitizenReport], int]:
        """Query moderation queue (pending reports) ordered oldest first by default."""
        return self.list_reports(
            status_filter="pending",
            event_type=event_type,
            location_id=location_id,
            from_time=from_time,
            to_time=to_time,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    def list_reviews_for_report(self, report_id: uuid.UUID) -> list[ReportReview]:
        """Retrieve review history for a report with reviewer user eager loaded."""
        return list(
            self.db.execute(
                select(ReportReview)
                .options(joinedload(ReportReview.reviewer))
                .where(ReportReview.report_id == report_id)
                .order_by(ReportReview.created_at.asc())
            )
            .scalars()
            .all()
        )

    def add_review(
        self,
        report_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        from_status: str,
        to_status: str,
        private_notes: str | None,
        reason_code: str | None,
        created_at: datetime,
    ) -> ReportReview:
        """Record an immutable moderation review entry."""
        review = ReportReview(
            report_id=report_id,
            reviewer_id=reviewer_id,
            from_status=from_status,
            to_status=to_status,
            private_notes=private_notes,
            reason_code=reason_code,
            created_at=created_at,
        )
        self.db.add(review)
        return review

    def add_audit_event(
        self,
        actor_user_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, Any] | None,
        ip_hash: str | None = None,
        created_at: datetime | None = None,
    ) -> AuditEvent:
        """Record an immutable audit event."""
        event = AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            event_metadata=metadata,
            ip_hash=ip_hash,
            created_at=created_at or datetime.now(UTC),
        )
        self.db.add(event)
        return event
