from app.schemas.common import CollectionResponse
"""Admin schemas for source management, manual ingestion triggers, and run tracking."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta


class LastRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    trigger: str
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    records_fetched: int
    inserted: int
    updated: int
    skipped: int
    failed: int
    error_summary: str | None = None


class DataSourceAdminItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_name: str
    source_type: str
    adapter_key: str
    trust_level: str
    is_enabled: bool
    interval_seconds: int
    configured: bool
    freshness: str = "never"
    attribution_text: str
    license_url: str | None = None
    homepage_url: str | None = None
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    last_run: LastRunSummary | None = None


class DataSourceListResponse(CollectionResponse):
    items: list[DataSourceAdminItem]


class DataSourceUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool | None = None
    interval_seconds: int | None = Field(None, ge=300, le=86400)
    display_name: str | None = Field(None, min_length=1, max_length=100)
    attribution_text: str | None = Field(None, min_length=1)
    config: dict[str, Any] | None = None


class IngestionRunTriggerResponse(BaseModel):
    run_id: int
    status: str = "queued"


class IngestionRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    source_name: str
    trigger: str
    triggered_by: uuid.UUID | None = None
    status: str
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    records_fetched: int
    inserted: int
    updated: int
    skipped: int
    failed: int
    error_summary: str | None = None


class IngestionRunDetail(IngestionRunSummary):
    details: dict[str, Any] | None = None


class IngestionRunListResponse(BaseModel):
    items: list[IngestionRunSummary]
    total: int
    limit: int
    offset: int
    pagination: PaginationMeta | None = None
