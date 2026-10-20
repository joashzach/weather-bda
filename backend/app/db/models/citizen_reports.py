"""Citizen reports table storing crowd-sourced severe weather and disaster observations."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CitizenReport(Base):
    __tablename__ = "citizen_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    location_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tracking_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    location = relationship("Location")
    reviewer = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('heavy_rain', 'flood', 'heatwave', 'cold_wave', 'storm', 'cyclone', 'drought', 'landslide', 'lightning', 'hail', 'fog', 'other')",
            name="ck_citizen_reports_event_type",
        ),
        CheckConstraint(
            "severity IS NULL OR severity IN ('low', 'moderate', 'high', 'extreme')",
            name="ck_citizen_reports_severity",
        ),
        CheckConstraint(
            "length(description) >= 10 AND length(description) <= 2000",
            name="ck_citizen_reports_description_len",
        ),
        CheckConstraint(
            "latitude >= -90.00000 AND latitude <= 90.00000", name="ck_citizen_reports_latitude"
        ),
        CheckConstraint(
            "longitude >= -180.00000 AND longitude <= 180.00000",
            name="ck_citizen_reports_longitude",
        ),
        CheckConstraint(
            "status IN ('pending', 'verified', 'rejected')", name="ck_citizen_reports_status"
        ),
        CheckConstraint(
            "(status = 'pending' AND reviewed_at IS NULL) OR (status != 'pending' AND reviewed_at IS NOT NULL)",
            name="ck_citizen_reports_reviewed_at",
        ),
        Index("ix_citizen_reports_status_submitted", "status", "submitted_at"),
        Index("ix_citizen_reports_event_type_status", "event_type", "status"),
        Index(
            "ix_citizen_reports_location_status_event_time",
            "location_id",
            "status",
            desc("event_time"),
        ),
        Index("ix_citizen_reports_event_time", desc("event_time")),
    )
