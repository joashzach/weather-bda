from app.schemas.common import CollectionResponse
"""Pydantic schemas for citizen weather/disaster reports, evidence, and moderation reviews."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.locations import LocationPublic
from app.schemas.users import UserPublic

EvidenceKind = Literal["photo", "video", "link", "other"]
SeverityLevel = Literal["low", "moderate", "high", "extreme"]


class EvidenceCreate(BaseModel):
    type: EvidenceKind = Field(..., description="Evidence type: photo, video, link, other")
    url: str = Field(
        ..., max_length=2048, description="URL pointing to evidence media or reference"
    )
    description: str = Field("", max_length=200, description="Brief description of the evidence")
    model_config = ConfigDict(extra="forbid")


class EvidencePublic(BaseModel):
    type: str
    description: str
    has_link: bool = True
    model_config = ConfigDict(extra="forbid")


class EvidenceStaff(BaseModel):
    type: str
    url: str
    description: str
    has_link: bool = True
    model_config = ConfigDict(extra="forbid")


class CitizenReportCreate(BaseModel):
    event_type: str = Field(..., description="Classification of weather or disaster event")
    severity: SeverityLevel | None = Field(None, description="Reported severity level")
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed description of the event (10-2000 chars)",
    )
    location_name: str | None = Field(
        None, max_length=200, description="Human-readable landmark or address"
    )
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude")
    event_time: datetime = Field(..., description="ISO 8601 UTC timestamp when event occurred")
    evidence: list[EvidenceCreate] = Field(
        default_factory=list,
        max_length=5,
        description="Up to 5 evidence metadata items",
    )
    contact_email: EmailStr | None = Field(
        None, description="Optional private contact email for verification"
    )
    model_config = ConfigDict(extra="forbid")


class CitizenReportCreatedResponse(BaseModel):
    id: uuid.UUID
    status: Literal["pending"] = "pending"
    submitted_at: datetime
    tracking_token: str = Field(
        ...,
        description="Single-use private token allowing caller to query status of unverified report",
    )
    model_config = ConfigDict(extra="forbid")


class CitizenReportPublic(BaseModel):
    id: uuid.UUID
    event_type: str
    severity: str | None
    description: str
    location_name: str | None
    latitude: float
    longitude: float
    location: LocationPublic | None = None
    event_time: datetime
    evidence: list[EvidencePublic]
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None = None
    model_config = ConfigDict(extra="forbid")


class CitizenReportStaff(BaseModel):
    id: uuid.UUID
    event_type: str
    severity: str | None
    description: str
    location_name: str | None
    latitude: float
    longitude: float
    location: LocationPublic | None = None
    event_time: datetime
    evidence: list[EvidenceStaff]
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None = None
    contact_email: str | None = None
    row_version: int
    reviewed_by: UserPublic | None = None
    model_config = ConfigDict(extra="forbid")


class ReportReviewDecision(BaseModel):
    decision: Literal["verify", "reject", "reopen"] = Field(
        ..., description="Review action: verify, reject, reopen"
    )
    notes: str | None = Field(
        None, max_length=2000, description="Private reviewer notes explaining the decision"
    )
    reason_code: str | None = Field(
        None, max_length=50, description="Structured reason code (e.g. duplicate, spam, verified)"
    )
    expected_row_version: int = Field(
        ..., description="Optimistic locking version expected on current report"
    )
    model_config = ConfigDict(extra="forbid")


class ReportReviewItem(BaseModel):
    id: int
    reviewer: UserPublic
    from_status: str
    to_status: str
    reason_code: str | None
    private_notes: str | None
    created_at: datetime
    model_config = ConfigDict(extra="forbid")


class ReportReviewsResponse(CollectionResponse):
    items: list[ReportReviewItem]
    model_config = ConfigDict(extra="forbid")
