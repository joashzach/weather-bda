"""Integration tests for IngestionWorker, stale run recovery, and overlap prevention."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import IngestionStatus
from app.db.models.data_sources import DataSource
from app.db.models.ingestion_runs import IngestionRun
from app.db.models.locations import Location
from app.worker import IngestionWorker
from tests.conftest import TestingSessionLocal


def test_worker_recover_stale_runs(setup_test_db):
    with TestingSessionLocal() as db:
        source = DataSource(
            name="stale_test_source",
            display_name="Stale Test",
            source_type="weather_api",
            adapter_key="open_meteo",
            trust_level="provider_model",
            attribution_text="Test",
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        source_id = source.id

        # Stale run: started 1200 seconds ago (threshold is 900)
        old_time = datetime.now(UTC) - timedelta(seconds=1200)
        stale_run = IngestionRun(
            source_id=source_id,
            trigger="scheduled",
            status=IngestionStatus.RUNNING,
            queued_at=old_time,
            started_at=old_time,
        )
        db.add(stale_run)
        db.commit()
        run_id = stale_run.id

    try:
        settings = Settings(INGESTION_RUN_TIMEOUT_SECONDS=900)
        worker = IngestionWorker(session_factory=TestingSessionLocal, settings=settings)

        recovered = worker.recover_stale_runs()
        assert recovered >= 1

        with TestingSessionLocal() as db:
            run = db.get(IngestionRun, run_id)
            assert run is not None
            assert run.status == IngestionStatus.ABANDONED
            assert "exceeding execution timeout" in run.error_summary
    finally:
        with TestingSessionLocal() as db:
            run = db.get(IngestionRun, run_id)
            if run:
                db.delete(run)
            src = db.get(DataSource, source_id)
            if src:
                db.delete(src)
            db.commit()


def test_worker_overlap_prevention_via_unique_index(db_session: Session):
    source = DataSource(
        name="overlap_test_source",
        display_name="Overlap Test",
        source_type="weather_api",
        adapter_key="open_meteo",
        trust_level="provider_model",
        attribution_text="Test",
    )
    db_session.add(source)
    db_session.commit()

    run1 = IngestionRun(
        source_id=source.id,
        trigger="manual",
        status=IngestionStatus.QUEUED,
        queued_at=datetime.now(UTC),
    )
    db_session.add(run1)
    db_session.commit()

    # Attempting to add another queued/running run for same source must trigger DB unique index conflict
    run2 = IngestionRun(
        source_id=source.id,
        trigger="scheduled",
        status=IngestionStatus.RUNNING,
        queued_at=datetime.now(UTC),
    )
    db_session.add(run2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_worker_poll_and_execute_queued_run(setup_test_db, monkeypatch):
    with TestingSessionLocal() as db:
        source = DataSource(
            name="poll_test_source",
            display_name="Poll Test",
            source_type="weather_api",
            adapter_key="open_meteo",
            trust_level="provider_model",
            is_enabled=True,
            attribution_text="Test",
            config={"past_days": 1, "forecast_days": 1},
        )
        loc = Location(
            slug="worker_test_loc",
            name="Worker Loc",
            region="Test Region",
            country_code="IN",
            latitude=12.97,
            longitude=77.59,
            is_active=True,
        )
        db.add_all([source, loc])
        db.commit()
        db.refresh(source)
        db.refresh(loc)
        source_id = source.id
        loc_id = loc.id

        # Create queued run
        queued_run = IngestionRun(
            source_id=source_id,
            trigger="manual",
            status=IngestionStatus.QUEUED,
            queued_at=datetime.now(UTC),
        )
        db.add(queued_run)
        db.commit()
        run_id = queued_run.id

    try:
        from app.ingestion.normalizers import NormalizedWeatherRecord

        mock_record = NormalizedWeatherRecord(
            source_id=source_id,
            location_id=loc_id,
            valid_at=datetime.now(UTC),
            fetched_at=datetime.now(UTC),
            record_kind="observation",
            measurement_basis="model_analysis",
            temperature_c=25.0,
            content_hash="mock_hash_" + "0" * 54,
        )
        mock_run = MagicMock()
        mock_run.return_value = MagicMock(
            records=[mock_record], news_records=[], errors=[], fetched_count=1, failed_count=0
        )
        monkeypatch.setattr("app.ingestion.adapters.open_meteo.OpenMeteoAdapter.run", mock_run)

        worker = IngestionWorker(session_factory=TestingSessionLocal)
        processed = worker.poll_queued_runs()
        assert processed == 1

        with TestingSessionLocal() as db:
            run = db.get(IngestionRun, run_id)
            assert run is not None
            assert run.status in (IngestionStatus.SUCCEEDED, IngestionStatus.PARTIAL)
            assert run.started_at is not None
            assert run.finished_at is not None
    finally:
        from sqlalchemy import text

        with TestingSessionLocal() as db:
            db.execute(text("DELETE FROM weather_records"))
            run = db.get(IngestionRun, run_id)
            if run:
                db.delete(run)
            loc = db.get(Location, loc_id)
            if loc:
                db.delete(loc)
            src = db.get(DataSource, source_id)
            if src:
                db.delete(src)
            db.commit()


def test_worker_sync_jobs_and_scheduled_tick(setup_test_db, monkeypatch):
    settings = Settings(INGESTION_ENABLED=True)
    worker = IngestionWorker(session_factory=TestingSessionLocal, settings=settings)

    with TestingSessionLocal() as db:
        source = DataSource(
            name="scheduled_tick_source",
            display_name="Scheduled Source",
            source_type="weather_api",
            adapter_key="open_meteo",
            trust_level="provider_model",
            is_enabled=True,
            interval_seconds=600,
            attribution_text="Test",
            config={"past_days": 1, "forecast_days": 1},
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        source_id = source.id

    try:
        # 1. Sync jobs with INGESTION_ENABLED=True
        worker.sync_scheduled_jobs()
        job = worker.scheduler.get_job(f"source_job_{source_id}")
        assert job is not None

        # 2. Sync jobs with INGESTION_ENABLED=False removes the job
        worker.settings.INGESTION_ENABLED = False
        worker.sync_scheduled_jobs()
        assert worker.scheduler.get_job(f"source_job_{source_id}") is None
        worker.settings.INGESTION_ENABLED = True

        # 3. Scheduled tick execution with mock run
        mock_pipeline_run = MagicMock()
        monkeypatch.setattr(worker.pipeline, "execute_run", mock_pipeline_run)
        worker.trigger_scheduled_tick(source_id=source_id, source_name="scheduled_tick_source")
        assert mock_pipeline_run.called

        # 4. Trigger scheduled tick when active run already exists skips cleanly
        mock_pipeline_run.reset_mock()
        worker.trigger_scheduled_tick(source_id=source_id, source_name="scheduled_tick_source")
        assert not mock_pipeline_run.called
    finally:
        with TestingSessionLocal() as db:
            from sqlalchemy import text

            db.execute(text(f"DELETE FROM ingestion_runs WHERE source_id = {source_id}"))
            src = db.get(DataSource, source_id)
            if src:
                db.delete(src)
            db.commit()


def test_worker_lifecycle():
    worker = IngestionWorker(session_factory=TestingSessionLocal)
    worker.start()
    assert worker._is_running is True
    assert worker.scheduler.running is True
    worker.stop()
    assert worker._is_running is False
