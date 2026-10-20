"""Admin service managing data sources, audit logging, and manual ingestion triggers."""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.enums import IngestionStatus, IngestionTrigger
from app.core.http_client import SafeHttpClient
from app.core.logging import get_logger
from app.db.models.data_sources import DataSource
from app.ingestion.adapters import ADAPTER_REGISTRY
from app.repositories.audit import AuditRepository
from app.repositories.ingestion import IngestionRunRepository
from app.repositories.sources import DataSourceRepository
from app.schemas.admin import (
    DataSourceAdminItem,
    DataSourceListResponse,
    DataSourceUpdatePayload,
    IngestionRunDetail,
    IngestionRunListResponse,
    IngestionRunSummary,
    IngestionRunTriggerResponse,
    LastRunSummary,
)
from app.schemas.common import PaginationMeta

logger = get_logger("app.services.admin")

SENSITIVE_KEY_PATTERN = re.compile(r"(key|token|secret|password|auth)", re.IGNORECASE)
QUERY_SECRET_PATTERN = re.compile(r"([?&](?:api-?key|token|secret|password)=)[^&]+", re.IGNORECASE)


def sanitize_value(val: Any) -> Any:
    """Recursively sanitize sensitive fields and query secrets from data structures."""
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            if SENSITIVE_KEY_PATTERN.search(k):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_value(v)
        return sanitized
    if isinstance(val, list):
        return [sanitize_value(item) for item in val]
    if isinstance(val, str):
        return QUERY_SECRET_PATTERN.sub(r"\1[REDACTED]", val)
    return val


def _compute_freshness(src: DataSource) -> str:
    """Compute data source freshness enum ('fresh', 'stale', 'never', 'disabled')."""
    if not src.is_enabled:
        return "disabled"
    if src.last_success_at is None:
        return "never"
    now = datetime.now(UTC)
    last_success = (
        src.last_success_at
        if src.last_success_at.tzinfo
        else src.last_success_at.replace(tzinfo=UTC)
    )
    diff_sec = (now - last_success).total_seconds()
    return "fresh" if diff_sec <= (2 * src.interval_seconds) else "stale"


class AdminService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.source_repo = DataSourceRepository(db)
        self.ingestion_repo = IngestionRunRepository(db)
        self.audit_repo = AuditRepository(db)

    def list_sources(self) -> DataSourceListResponse:
        """List all configured and candidate sources with last run summary and configured status."""
        sources = self.source_repo.list_all()
        items: list[DataSourceAdminItem] = []

        for src in sources:
            adapter_cls = ADAPTER_REGISTRY.get(src.adapter_key)
            is_cfg = False
            if adapter_cls:
                is_cfg = adapter_cls().is_configured(src, self.settings)

            last_run_model = self.ingestion_repo.get_last_run_for_source(src.id)
            last_run_summary = None
            if last_run_model:
                last_run_summary = LastRunSummary(
                    id=last_run_model.id,
                    status=last_run_model.status,
                    trigger=last_run_model.trigger,
                    queued_at=last_run_model.queued_at,
                    started_at=last_run_model.started_at,
                    finished_at=last_run_model.finished_at,
                    records_fetched=last_run_model.records_fetched,
                    inserted=last_run_model.inserted,
                    updated=last_run_model.updated,
                    skipped=last_run_model.skipped,
                    failed=last_run_model.failed,
                    error_summary=sanitize_value(last_run_model.error_summary),
                )

            items.append(
                DataSourceAdminItem(
                    id=src.id,
                    name=src.name,
                    display_name=src.display_name,
                    source_type=src.source_type,
                    adapter_key=src.adapter_key,
                    trust_level=src.trust_level,
                    is_enabled=src.is_enabled,
                    interval_seconds=src.interval_seconds,
                    configured=is_cfg,
                    freshness=_compute_freshness(src),
                    attribution_text=src.attribution_text,
                    license_url=src.license_url,
                    homepage_url=src.homepage_url,
                    last_attempt_at=src.last_attempt_at,
                    last_success_at=src.last_success_at,
                    config=sanitize_value(src.config or {}),
                    last_run=last_run_summary,
                )
            )

        return DataSourceListResponse(items=items)

    def update_source(
        self,
        source_id: int,
        payload: DataSourceUpdatePayload,
        actor_user_id: uuid.UUID,
        ip_hash: str | None = None,
    ) -> DataSourceAdminItem:
        """Update source configuration, interval, or enabled status with strict validation and auditing."""
        source = self.source_repo.get_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "source_not_found",
                    "message": f"Source with ID {source_id} not found",
                },
            )

        adapter_cls = ADAPTER_REGISTRY.get(source.adapter_key)
        adapter = adapter_cls() if adapter_cls else None

        # Build candidate updated model for pre-validation
        target_enabled = source.is_enabled if payload.is_enabled is None else payload.is_enabled
        target_config = dict(source.config or {})
        if payload.config is not None:
            # Validate any URLs in config against SSRF rules
            for k, v in payload.config.items():
                if isinstance(v, str) and (v.startswith("http://") or v.startswith("https://")):
                    try:
                        SafeHttpClient(self.settings).validate_url(v)
                    except Exception as exc:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={
                                "code": "ssrf_violation",
                                "message": f"Config field '{k}' failed SSRF validation: {exc}",
                            },
                        ) from exc
            target_config.update(payload.config)

        # Check: Enabling a source that is not configured returns 409 source_not_configured
        if target_enabled:
            temp_source = DataSource(
                name=source.name,
                adapter_key=source.adapter_key,
                config=target_config,
            )
            if not adapter or not adapter.is_configured(temp_source, self.settings):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "source_not_configured",
                        "message": f"Source '{source.name}' cannot be enabled because required credentials or config are missing.",
                    },
                )

        # Apply updates
        changed_fields = []
        if payload.is_enabled is not None and payload.is_enabled != source.is_enabled:
            source.is_enabled = payload.is_enabled
            changed_fields.append("is_enabled")
        if (
            payload.interval_seconds is not None
            and payload.interval_seconds != source.interval_seconds
        ):
            source.interval_seconds = payload.interval_seconds
            changed_fields.append("interval_seconds")
        if payload.display_name is not None and payload.display_name != source.display_name:
            source.display_name = payload.display_name
            changed_fields.append("display_name")
        if (
            payload.attribution_text is not None
            and payload.attribution_text != source.attribution_text
        ):
            source.attribution_text = payload.attribution_text
            changed_fields.append("attribution_text")
        if payload.config is not None:
            source.config = target_config
            changed_fields.append("config")

        # Record audit event
        self.audit_repo.create_event(
            action="update_source",
            entity_type="data_source",
            entity_id=str(source.id),
            actor_user_id=actor_user_id,
            metadata={"changed_fields": changed_fields, "source_name": source.name},
            ip_hash=ip_hash,
        )

        self.db.commit()
        self.db.refresh(source)

        is_cfg = adapter.is_configured(source, self.settings) if adapter else False
        last_run_model = self.ingestion_repo.get_last_run_for_source(source.id)
        last_run_summary = None
        if last_run_model:
            last_run_summary = LastRunSummary(
                id=last_run_model.id,
                status=last_run_model.status,
                trigger=last_run_model.trigger,
                queued_at=last_run_model.queued_at,
                started_at=last_run_model.started_at,
                finished_at=last_run_model.finished_at,
                records_fetched=last_run_model.records_fetched,
                inserted=last_run_model.inserted,
                updated=last_run_model.updated,
                skipped=last_run_model.skipped,
                failed=last_run_model.failed,
                error_summary=sanitize_value(last_run_model.error_summary),
            )

        return DataSourceAdminItem(
            id=source.id,
            name=source.name,
            display_name=source.display_name,
            source_type=source.source_type,
            adapter_key=source.adapter_key,
            trust_level=source.trust_level,
            is_enabled=source.is_enabled,
            interval_seconds=source.interval_seconds,
            configured=is_cfg,
            freshness=_compute_freshness(source),
            attribution_text=source.attribution_text,
            license_url=source.license_url,
            homepage_url=source.homepage_url,
            last_attempt_at=source.last_attempt_at,
            last_success_at=source.last_success_at,
            config=sanitize_value(source.config or {}),
            last_run=last_run_summary,
        )

    def trigger_ingestion(
        self,
        source_name: str,
        actor_user_id: uuid.UUID,
    ) -> IngestionRunTriggerResponse:
        """Enqueue a manual ingestion run. Enforces overlap prevention and adapter configuration."""
        source = self.source_repo.get_by_name(source_name)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "source_not_found",
                    "message": f"Source '{source_name}' does not exist",
                },
            )

        adapter_cls = ADAPTER_REGISTRY.get(source.adapter_key)
        if not adapter_cls or not adapter_cls().is_configured(source, self.settings):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "source_not_configured",
                    "message": f"Source '{source.name}' is not configured with required credentials or parameters.",
                },
            )

        # Race-safe overlap check
        active_run = self.ingestion_repo.get_active_run_for_source(source.id)
        if active_run:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "already_running",
                    "message": f"An ingestion run is already queued or running for source '{source_name}'.",
                },
            )

        try:
            run = self.ingestion_repo.create_queued_run(
                source_id=source.id,
                trigger=IngestionTrigger.MANUAL,
                triggered_by=actor_user_id,
            )
            self.db.commit()
            self.db.refresh(run)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "already_running",
                    "message": f"An ingestion run is already queued or running for source '{source_name}'.",
                },
            ) from exc

        return IngestionRunTriggerResponse(run_id=run.id, status=IngestionStatus.QUEUED)

    def list_ingestion_runs(
        self,
        source: str | None = None,
        run_status: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        page: int = 1,
        page_size: int = 20,
    ) -> IngestionRunListResponse:
        """List ingestion runs with filtering and pagination."""
        runs, total = self.ingestion_repo.list_runs(
            source_name=source,
            status=run_status,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
            offset=offset,
        )

        items = [
            IngestionRunSummary(
                id=r.id,
                source_id=r.source_id,
                source_name=r.source.name if r.source else "unknown",
                trigger=r.trigger,
                triggered_by=r.triggered_by,
                status=r.status,
                queued_at=r.queued_at,
                started_at=r.started_at,
                finished_at=r.finished_at,
                records_fetched=r.records_fetched,
                inserted=r.inserted,
                updated=r.updated,
                skipped=r.skipped,
                failed=r.failed,
                error_summary=sanitize_value(r.error_summary),
            )
            for r in runs
        ]

        pages = (total + limit - 1) // limit if total > 0 else 1
        current_page = (offset // limit) + 1 if limit > 0 else 1
        return IngestionRunListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            pagination=PaginationMeta(page=current_page, page_size=limit, total=total, pages=pages),
        )

    def get_ingestion_run(self, run_id: int) -> IngestionRunDetail:
        """Get details for a single ingestion run with sanitized errors and metadata."""
        run = self.ingestion_repo.get_by_id(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "run_not_found",
                    "message": f"Ingestion run with ID {run_id} not found",
                },
            )

        return IngestionRunDetail(
            id=run.id,
            source_id=run.source_id,
            source_name=run.source.name if run.source else "unknown",
            trigger=run.trigger,
            triggered_by=run.triggered_by,
            status=run.status,
            queued_at=run.queued_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            records_fetched=run.records_fetched,
            inserted=run.inserted,
            updated=run.updated,
            skipped=run.skipped,
            failed=run.failed,
            error_summary=sanitize_value(run.error_summary),
            details=sanitize_value(run.details),
        )
