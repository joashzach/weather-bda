"""Reusable ingestion pipeline enforcing failure isolation, deduplication, and counting per PRD Section 8.1."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.core.enums import IngestionStatus, IngestionTrigger
from app.core.http_client import SafeHttpClient
from app.core.logging import get_logger
from app.db.models.ingestion_runs import IngestionRun
from app.ingestion.adapters import ADAPTER_REGISTRY
from app.repositories.locations import LocationRepository
from app.repositories.sources import DataSourceRepository
from app.repositories.weather import WeatherRepository

logger = get_logger("app.ingestion.pipeline")


class IngestionPipeline:
    def __init__(self, session_factory: sessionmaker, settings: Settings | None = None) -> None:
        self.session_factory = session_factory
        self.settings = settings or get_settings()

    def execute_run(
        self,
        source_id: int,
        trigger: IngestionTrigger | str = IngestionTrigger.MANUAL,
        triggered_by: uuid.UUID | None = None,
        existing_run_id: int | None = None,
    ) -> IngestionRun:
        """Execute full ingestion pipeline for the specified source. Isolates transactions per target."""
        started_at = datetime.now(UTC)

        # 1. Initialize or load IngestionRun record
        with self.session_factory() as db:
            source_repo = DataSourceRepository(db)
            source = source_repo.get_by_id(source_id)
            if not source:
                raise ValueError(f"DataSource with id {source_id} not found.")

            if existing_run_id:
                run = db.get(IngestionRun, existing_run_id)
                if not run:
                    raise ValueError(f"IngestionRun with id {existing_run_id} not found.")
                run.status = IngestionStatus.RUNNING
                run.started_at = started_at
            else:
                run = IngestionRun(
                    source_id=source.id,
                    trigger=str(trigger),
                    triggered_by=triggered_by,
                    status=IngestionStatus.RUNNING,
                    queued_at=started_at,
                    started_at=started_at,
                )
                db.add(run)
            db.commit()
            db.refresh(run)
            run_id = run.id
            adapter_key = source.adapter_key

        # 2. Check adapter registration and configuration
        adapter_cls = ADAPTER_REGISTRY.get(adapter_key)
        if not adapter_cls:
            self._finalize_run(
                run_id=run_id,
                source_id=source_id,
                status=IngestionStatus.FAILED,
                error_summary=f"No registered adapter found for key '{adapter_key}'",
            )
            with self.session_factory() as db:
                return db.get(IngestionRun, run_id)

        adapter = adapter_cls()

        with self.session_factory() as db:
            source = DataSourceRepository(db).get_by_id(source_id)
            if not source or not adapter.is_configured(source, self.settings):
                self._finalize_run(
                    run_id=run_id,
                    source_id=source_id,
                    status=IngestionStatus.FAILED,
                    error_summary=f"Adapter '{adapter_key}' is not configured or missing requirements",
                )
                with self.session_factory() as db_final:
                    return db_final.get(IngestionRun, run_id)

        # 3. Retrieve targets
        with self.session_factory() as db:
            location_repo = LocationRepository(db)
            targets = list(location_repo.list_active())

        records_fetched = 0
        inserted_count = 0
        updated_count = 0
        skipped_count = 0
        failed_count = 0
        accumulated_errors: list[dict[str, str]] = []

        # 4. Ingest each target location in its own isolated transaction
        with SafeHttpClient() as http_client:
            for target in targets:
                target_result = adapter.run(
                    source=source,
                    targets=[target],
                    http_client=http_client,
                    settings=self.settings,
                )

                records_fetched += target_result.fetched_count
                failed_count += target_result.failed_count

                for err in target_result.errors:
                    accumulated_errors.append(
                        {
                            "target": err.target_key,
                            "error_code": err.error_code,
                            "message": err.message,
                        }
                    )

                if not target_result.records:
                    continue

                # Persist in dedicated transaction for failure isolation
                try:
                    with self.session_factory() as target_db:
                        weather_repo = WeatherRepository(target_db)
                        records_dicts = [
                            {**rec.model_dump(), "ingestion_run_id": run_id}
                            for rec in target_result.records
                        ]
                        stats = weather_repo.bulk_upsert(records_dicts)
                        target_db.commit()

                        inserted_count += stats["inserted"]
                        updated_count += stats["updated"]
                        skipped_count += stats["skipped"]
                except Exception as e:
                    logger.error(
                        "target_persistence_failed",
                        target=getattr(target, "slug", str(target)),
                        error=str(e),
                    )
                    failed_count += len(target_result.records)
                    accumulated_errors.append(
                        {
                            "target": getattr(target, "slug", str(target)),
                            "error_code": "db_persistence_error",
                            "message": f"Failed to persist records: {e}"[:1000],
                        }
                    )

        # 5. Determine final run status
        saved_count = inserted_count + updated_count
        if saved_count > 0 and (failed_count > 0 or len(accumulated_errors) > 0):
            final_status = IngestionStatus.PARTIAL
        elif saved_count > 0 and failed_count == 0 and len(accumulated_errors) == 0:
            final_status = IngestionStatus.SUCCEEDED
        elif records_fetched > 0 and skipped_count == records_fetched and failed_count == 0:
            # Everything fetched was valid and skipped (unchanged) -> succeeded!
            final_status = IngestionStatus.SUCCEEDED
        else:
            final_status = IngestionStatus.FAILED

        error_summary = None
        if accumulated_errors:
            error_summary = f"{len(accumulated_errors)} error(s) occurred during ingestion: {accumulated_errors[0]['message']}"[
                :1000
            ]

        # 6. Finalize run and update source timestamps
        self._finalize_run(
            run_id=run_id,
            source_id=source_id,
            status=final_status,
            records_fetched=records_fetched,
            inserted=inserted_count,
            updated=updated_count,
            skipped=skipped_count,
            failed=failed_count,
            error_summary=error_summary,
            errors=accumulated_errors,
        )

        with self.session_factory() as db:
            return db.get(IngestionRun, run_id)

    def _finalize_run(
        self,
        run_id: int,
        source_id: int,
        status: IngestionStatus | str,
        records_fetched: int = 0,
        inserted: int = 0,
        updated: int = 0,
        skipped: int = 0,
        failed: int = 0,
        error_summary: str | None = None,
        errors: list[dict[str, str]] | None = None,
    ) -> None:
        """Update IngestionRun row and update source last_attempt_at / last_success_at."""
        now = datetime.now(UTC)
        with self.session_factory() as db:
            run = db.get(IngestionRun, run_id)
            if run:
                run.status = str(status)
                run.finished_at = now
                run.records_fetched = records_fetched
                run.inserted = inserted
                run.updated = updated
                run.skipped = skipped
                run.failed = failed
                run.error_summary = error_summary
                if errors:
                    run.details = {
                        "errors": errors[:50]
                    }  # PRD Section 4.8: truncated to 50 entries
                db.flush()

            source_repo = DataSourceRepository(db)
            last_success = (
                now if str(status) in (IngestionStatus.SUCCEEDED, IngestionStatus.PARTIAL) else None
            )
            source_repo.update_timestamps(
                source_id=source_id,
                last_attempt_at=now,
                last_success_at=last_success,
            )
            db.commit()
