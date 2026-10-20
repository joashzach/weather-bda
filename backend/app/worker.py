"""Standalone background worker process conforming to PRD Section 8.5."""

import signal
import sys
import threading
import time
from datetime import UTC, datetime
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.core.enums import IngestionStatus, IngestionTrigger
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.ingestion.adapters import ADAPTER_REGISTRY
from app.ingestion.pipeline import IngestionPipeline
from app.repositories.ingestion import IngestionRunRepository
from app.repositories.sources import DataSourceRepository

logger = get_logger("app.worker")


class IngestionWorker:
    def __init__(
        self,
        session_factory: sessionmaker = SessionLocal,
        settings: Settings | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings or get_settings()
        self.pipeline = IngestionPipeline(
            session_factory=self.session_factory, settings=self.settings
        )
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self._is_running = False
        self._stop_event = threading.Event()
        self._active_run_id: int | None = None

    def recover_stale_runs(self) -> int:
        """Abandon any runs remaining in 'running' state past INGESTION_RUN_TIMEOUT_SECONDS."""
        with self.session_factory() as db:
            repo = IngestionRunRepository(db)
            abandoned_count = repo.abandon_stale_runs(self.settings.INGESTION_RUN_TIMEOUT_SECONDS)
            db.commit()
            if abandoned_count > 0:
                logger.warning(
                    "Recovered stale ingestion runs on worker startup",
                    abandoned_count=abandoned_count,
                    timeout_seconds=self.settings.INGESTION_RUN_TIMEOUT_SECONDS,
                )
            return abandoned_count

    def sync_scheduled_jobs(self) -> None:
        """Synchronize APScheduler jobs from the database every 60 seconds."""
        if not self.settings.INGESTION_ENABLED:
            # If scheduled ingestion is disabled, remove any existing source jobs
            for job in self.scheduler.get_jobs():
                if job.id.startswith("source_job_"):
                    self.scheduler.remove_job(job.id)
            logger.debug("Scheduled ingestion disabled via INGESTION_ENABLED=false")
            return

        with self.session_factory() as db:
            source_repo = DataSourceRepository(db)
            sources = source_repo.list_all()

            active_job_ids = set()
            for src in sources:
                adapter_cls = ADAPTER_REGISTRY.get(src.adapter_key)
                if not adapter_cls:
                    continue

                adapter = adapter_cls()
                is_cfg = adapter.is_configured(src, self.settings)

                job_id = f"source_job_{src.id}"

                # Scheduled jobs exist ONLY when is_enabled=True and is_configured=True
                if src.is_enabled and is_cfg:
                    active_job_ids.add(job_id)
                    existing_job = self.scheduler.get_job(job_id)

                    interval_sec = max(300, src.interval_seconds)
                    trigger = IntervalTrigger(seconds=interval_sec, jitter=5)

                    if existing_job:
                        # Update interval if modified
                        if existing_job.trigger.interval.total_seconds() != interval_sec:
                            self.scheduler.reschedule_job(job_id, trigger=trigger)
                            logger.info(
                                "Rescheduled ingestion job for source",
                                source_name=src.name,
                                interval_seconds=interval_sec,
                            )
                    else:
                        self.scheduler.add_job(
                            func=self.trigger_scheduled_tick,
                            trigger=trigger,
                            args=[src.id, src.name],
                            id=job_id,
                            name=f"Ingest {src.name}",
                            max_instances=1,
                            coalesce=True,
                            misfire_grace_time=60,
                        )
                        logger.info(
                            "Added scheduled ingestion job for source",
                            source_name=src.name,
                            interval_seconds=interval_sec,
                        )

            # Clean up jobs for sources that became disabled or unconfigured
            for job in self.scheduler.get_jobs():
                if job.id.startswith("source_job_") and job.id not in active_job_ids:
                    self.scheduler.remove_job(job.id)
                    logger.info("Removed inactive ingestion job", job_id=job.id)

    def trigger_scheduled_tick(self, source_id: int, source_name: str) -> None:
        """Scheduled tick: inserts a queued run (overlap prevented by index) and processes it."""
        logger.info(
            "Scheduled tick triggered for source", source_name=source_name, source_id=source_id
        )
        with self.session_factory() as db:
            ingestion_repo = IngestionRunRepository(db)
            active_run = ingestion_repo.get_active_run_for_source(source_id)
            if active_run:
                logger.info(
                    "Skipping scheduled tick: source already has active run",
                    source_name=source_name,
                    active_run_id=active_run.id,
                )
                return

            try:
                run = ingestion_repo.create_queued_run(
                    source_id=source_id,
                    trigger=IngestionTrigger.SCHEDULED,
                    triggered_by=None,
                )
                db.commit()
                run_id = run.id
            except IntegrityError:
                db.rollback()
                logger.info(
                    "Overlap prevented by unique index for scheduled tick",
                    source_name=source_name,
                )
                return

        # Execute run
        self._execute_single_run(run_id=run_id, source_id=source_id)

    def poll_queued_runs(self) -> int:
        """Poll queued runs using SELECT ... FOR UPDATE SKIP LOCKED and execute them."""
        processed = 0

        while not self._stop_event.is_set():
            run_id = None
            source_id = None

            with self.session_factory() as db:
                repo = IngestionRunRepository(db)
                run = repo.claim_next_queued_run()
                if not run:
                    break

                # Update status to running
                run.status = IngestionStatus.RUNNING
                run.started_at = datetime.now(UTC)
                db.commit()

                run_id = run.id
                source_id = run.source_id

            if run_id and source_id:
                self._execute_single_run(run_id=run_id, source_id=source_id)
                processed += 1

        return processed

    def _execute_single_run(self, run_id: int, source_id: int) -> None:
        """Execute a single run through the pipeline with error containment and active tracking."""
        self._active_run_id = run_id
        try:
            logger.info("Worker starting execution for run", run_id=run_id, source_id=source_id)
            self.pipeline.execute_run(
                source_id=source_id,
                existing_run_id=run_id,
            )
            logger.info("Worker finished execution for run", run_id=run_id)
        except Exception as exc:
            logger.exception(
                "Unexpected error executing run in worker", run_id=run_id, error=str(exc)
            )
            with self.session_factory() as db:
                repo = IngestionRunRepository(db)
                r = repo.get_by_id(run_id)
                if r and r.status in (IngestionStatus.QUEUED, IngestionStatus.RUNNING):
                    r.status = IngestionStatus.FAILED
                    r.finished_at = datetime.now(UTC)
                    r.error_summary = f"Worker unhandled crash: {exc}"[:1000]
                    db.commit()
        finally:
            self._active_run_id = None

    def start(self) -> None:
        """Start worker process, stale run recovery, and scheduler."""
        logger.info("Starting IngestionWorker background process...")
        self._is_running = True
        self._stop_event.clear()

        # 1. Stale-run recovery on startup
        self.recover_stale_runs()

        # 2. Add maintenance and polling jobs
        self.scheduler.add_job(
            func=self.sync_scheduled_jobs,
            trigger=IntervalTrigger(seconds=60),
            id="worker_sync_jobs",
            name="Sync Source Schedules",
            coalesce=True,
            max_instances=1,
        )

        self.scheduler.add_job(
            func=self.poll_queued_runs,
            trigger=IntervalTrigger(seconds=10),
            id="worker_poll_queued",
            name="Poll Queued Runs",
            coalesce=True,
            max_instances=1,
        )

        # Initial schedule sync
        self.sync_scheduled_jobs()
        # Immediate poll for any existing queued runs
        self.poll_queued_runs()

        self.scheduler.start()
        logger.info("IngestionWorker background scheduler started successfully.")

    def stop(self) -> None:
        """Gracefully stop worker and scheduler."""
        logger.info("Stopping IngestionWorker...")
        self._is_running = False
        self._stop_event.set()

        try:
            self.scheduler.shutdown(wait=True)
        except Exception as exc:
            logger.warning("Error shutting down scheduler", error=str(exc))

        # Check if an active run was in progress and mark abandoned
        if self._active_run_id:
            try:
                with self.session_factory() as db:
                    repo = IngestionRunRepository(db)
                    repo.mark_abandoned(
                        self._active_run_id,
                        reason="Worker terminated via graceful shutdown",
                    )
                    db.commit()
            except Exception as exc:
                logger.error("Failed to mark active run abandoned on shutdown", error=str(exc))

        logger.info("IngestionWorker stopped.")


def run_worker_process() -> None:
    """Entrypoint for `python -m app.worker` standalone process."""
    worker = IngestionWorker()

    def handle_signal(sig: int, _frame: Any) -> None:
        sig_name = signal.Signals(sig).name
        logger.info("Received termination signal", signal=sig_name)
        worker.stop()
        sys.exit(0)

    # Register OS signals
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    worker.start()

    logger.info("Worker process running. Press Ctrl+C to terminate.")
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        worker.stop()


if __name__ == "__main__":
    run_worker_process()
