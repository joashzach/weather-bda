"""Repository for querying, queueing, and tracking ingestion runs."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.enums import IngestionStatus, IngestionTrigger
from app.db.models.data_sources import DataSource
from app.db.models.ingestion_runs import IngestionRun


class IngestionRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, run_id: int) -> IngestionRun | None:
        return (
            self.db.execute(
                select(IngestionRun)
                .options(joinedload(IngestionRun.source))
                .where(IngestionRun.id == run_id)
            )
            .scalars()
            .first()
        )

    def get_active_run_for_source(self, source_id: int) -> IngestionRun | None:
        """Find an active (queued or running) run for this source."""
        stmt = (
            select(IngestionRun)
            .where(
                IngestionRun.source_id == source_id,
                IngestionRun.status.in_([IngestionStatus.QUEUED, IngestionStatus.RUNNING]),
            )
            .order_by(desc(IngestionRun.id))
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def get_last_run_for_source(self, source_id: int) -> IngestionRun | None:
        """Find the most recent ingestion run for this source regardless of status."""
        stmt = (
            select(IngestionRun)
            .where(IngestionRun.source_id == source_id)
            .order_by(desc(IngestionRun.id))
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def create_queued_run(
        self,
        source_id: int,
        trigger: IngestionTrigger | str = IngestionTrigger.MANUAL,
        triggered_by: uuid.UUID | None = None,
    ) -> IngestionRun:
        """Create a new queued ingestion run. Overlap is prevented by partial unique index."""
        now = datetime.now(UTC)
        run = IngestionRun(
            source_id=source_id,
            trigger=str(trigger),
            triggered_by=triggered_by,
            status=IngestionStatus.QUEUED,
            queued_at=now,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def claim_next_queued_run(self) -> IngestionRun | None:
        """Claim the next queued run using SELECT ... FOR UPDATE SKIP LOCKED."""
        stmt = (
            select(IngestionRun)
            .where(IngestionRun.status == IngestionStatus.QUEUED)
            .order_by(IngestionRun.queued_at.asc(), IngestionRun.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return self.db.execute(stmt).scalars().first()

    def mark_running(self, run_id: int) -> IngestionRun | None:
        run = self.get_by_id(run_id)
        if run and run.status == IngestionStatus.QUEUED:
            run.status = IngestionStatus.RUNNING
            run.started_at = datetime.now(UTC)
            self.db.flush()
        return run

    def mark_abandoned(self, run_id: int, reason: str = "Abandoned") -> IngestionRun | None:
        run = self.get_by_id(run_id)
        if run and run.status in (IngestionStatus.QUEUED, IngestionStatus.RUNNING):
            run.status = IngestionStatus.ABANDONED
            run.finished_at = datetime.now(UTC)
            run.error_summary = reason[:1000]
            self.db.flush()
        return run

    def abandon_stale_runs(self, timeout_seconds: int = 900) -> int:
        """Mark running runs older than timeout_seconds as abandoned."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=timeout_seconds)

        stmt = (
            update(IngestionRun)
            .where(
                IngestionRun.status == IngestionStatus.RUNNING,
                IngestionRun.started_at < cutoff,
            )
            .values(
                status=IngestionStatus.ABANDONED,
                finished_at=now,
                error_summary="Run abandoned due to exceeding execution timeout threshold",
            )
        )
        res = self.db.execute(stmt)
        self.db.flush()
        return res.rowcount

    def list_runs(
        self,
        source_name: str | None = None,
        status: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[Sequence[IngestionRun], int]:
        """List ingestion runs with optional filtering and pagination."""
        base_query = select(IngestionRun).join(DataSource)

        if source_name:
            base_query = base_query.where(DataSource.name == source_name.strip())
        if status:
            base_query = base_query.where(IngestionRun.status == status.strip())
        if from_time:
            base_query = base_query.where(IngestionRun.queued_at >= from_time)
        if to_time:
            base_query = base_query.where(IngestionRun.queued_at <= to_time)

        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # Paged query
        eff_limit = limit if limit is not None else page_size
        eff_offset = offset if offset is not None else (page - 1) * page_size
        paged_stmt = (
            base_query.options(joinedload(IngestionRun.source))
            .order_by(desc(IngestionRun.queued_at), desc(IngestionRun.id))
            .offset(eff_offset)
            .limit(eff_limit)
        )
        runs = self.db.execute(paged_stmt).scalars().all()
        return runs, total
