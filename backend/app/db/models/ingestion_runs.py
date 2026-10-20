"""Ingestion runs tracking execution state, metrics, errors, and preventing concurrent overlaps."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("data_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    source = relationship("DataSource")
    user = relationship("User")

    __table_args__ = (
        CheckConstraint("trigger IN ('scheduled', 'manual')", name="ck_ingestion_runs_trigger"),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'partial', 'failed', 'abandoned')",
            name="ck_ingestion_runs_status",
        ),
        CheckConstraint("records_fetched >= 0", name="ck_ingestion_runs_records_fetched"),
        CheckConstraint("inserted >= 0", name="ck_ingestion_runs_inserted"),
        CheckConstraint("updated >= 0", name="ck_ingestion_runs_updated"),
        CheckConstraint("skipped >= 0", name="ck_ingestion_runs_skipped"),
        CheckConstraint("failed >= 0", name="ck_ingestion_runs_failed"),
        # Partial unique index to race-safely prevent duplicate concurrent queued/running runs per source
        Index(
            "uq_ingestion_runs_source_active",
            "source_id",
            unique=True,
            postgresql_where=(status.in_(["queued", "running"])),
        ),
    )
