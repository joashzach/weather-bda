"""Integration tests for IngestionPipeline verifying transaction isolation, deduplication, and failure handling."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.orm import close_all_sessions

from app.core.config import get_settings
from app.core.enums import IngestionStatus, IngestionTrigger
from app.db.models.data_sources import DataSource
from app.db.models.locations import Location
from app.db.models.weather_records import WeatherRecord
from app.ingestion.adapters.base import AdapterResult, TargetError
from app.ingestion.adapters.open_meteo import OpenMeteoAdapter
from app.ingestion.normalizers import normalize_open_meteo_record
from app.ingestion.pipeline import IngestionPipeline
from tests.conftest import TestingSessionLocal, test_engine

settings = get_settings()


@pytest.fixture(autouse=True)
def clean_database(setup_test_db):
    """Clean tables before and after each test."""

    def _do_clean():
        close_all_sessions()
        with test_engine.begin() as conn:
            conn.execute(text("DELETE FROM weather_records"))
            conn.execute(text("DELETE FROM ingestion_runs"))
            conn.execute(text("DELETE FROM locations"))
            conn.execute(text("DELETE FROM data_sources"))

    _do_clean()
    yield
    _do_clean()


def _seed_source_and_locations():
    with TestingSessionLocal() as db:
        source = DataSource(
            name="open_meteo",
            display_name="Open-Meteo",
            source_type="weather_api",
            adapter_key="open_meteo",
            trust_level="provider_model",
            is_enabled=True,
            interval_seconds=3600,
            attribution_text="Weather data by Open-Meteo under CC BY 4.0",
        )
        db.add(source)

        loc1 = Location(
            slug="mumbai",
            name="Mumbai",
            region="Maharashtra",
            country_code="IN",
            latitude=19.076,
            longitude=72.877,
            is_active=True,
        )
        loc2 = Location(
            slug="delhi",
            name="Delhi",
            region="Delhi",
            country_code="IN",
            latitude=28.613,
            longitude=77.209,
            is_active=True,
        )
        db.add_all([loc1, loc2])
        db.commit()
        db.refresh(source)
        db.refresh(loc1)
        db.refresh(loc2)
        return source.id, loc1.id, loc2.id


def test_pipeline_successful_ingestion_and_deduplication(monkeypatch):
    source_id, loc1_id, _ = _seed_source_and_locations()
    pipeline = IngestionPipeline(session_factory=TestingSessionLocal)

    # Mock SafeHttpClient.get to return deterministic data
    mock_hourly_data = {
        "hourly": {
            "time": ["2026-10-20T10:00", "2026-10-20T11:00"],
            "temperature_2m": [28.5, 29.0],
            "apparent_temperature": [32.0, 33.0],
            "relative_humidity_2m": [70.0, 68.0],
            "precipitation": [0.0, 0.2],
            "rain": [0.0, 0.2],
            "precipitation_probability": [10, 30],
            "wind_speed_10m": [12.0, 14.0],
            "wind_gusts_10m": [18.0, 20.0],
            "wind_direction_10m": [210.0, 220.0],
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_hourly_data

    monkeypatch.setattr(
        "app.core.http_client.SafeHttpClient.get", lambda self, url, **kwargs: mock_resp
    )

    # 1. First run: should insert records for all active locations (2 locations * 2 records = 4 records)
    run1 = pipeline.execute_run(source_id=source_id, trigger=IngestionTrigger.MANUAL)
    assert run1.status == IngestionStatus.SUCCEEDED
    assert run1.records_fetched == 4
    assert run1.inserted == 4
    assert run1.skipped == 0
    assert run1.updated == 0
    assert run1.failed == 0

    with TestingSessionLocal() as db:
        records = db.query(WeatherRecord).all()
        assert len(records) == 4
        for r in records:
            assert len(r.content_hash) == 64
            assert r.ingestion_run_id == run1.id

        source = db.get(DataSource, source_id)
        assert source.last_attempt_at is not None
        assert source.last_success_at is not None

    # 2. Second run with EXACT same data: deduplication should skip all records
    run2 = pipeline.execute_run(source_id=source_id, trigger=IngestionTrigger.SCHEDULED)
    assert run2.status == IngestionStatus.SUCCEEDED
    assert run2.records_fetched == 4
    assert run2.inserted == 0
    assert run2.skipped == 4
    assert run2.updated == 0
    assert run2.failed == 0

    # 3. Third run: Modify temperature of one timestamp for all locations
    modified_hourly_data = {
        "hourly": {
            "time": ["2026-10-20T10:00", "2026-10-20T11:00"],
            "temperature_2m": [35.0, 29.0],  # 28.5 -> 35.0
            "apparent_temperature": [32.0, 33.0],
            "relative_humidity_2m": [70.0, 68.0],
            "precipitation": [0.0, 0.2],
            "rain": [0.0, 0.2],
            "precipitation_probability": [10, 30],
            "wind_speed_10m": [12.0, 14.0],
            "wind_gusts_10m": [18.0, 20.0],
            "wind_direction_10m": [210.0, 220.0],
        }
    }
    mock_resp.json.return_value = modified_hourly_data

    run3 = pipeline.execute_run(source_id=source_id)
    assert run3.status == IngestionStatus.SUCCEEDED
    assert run3.records_fetched == 4
    assert run3.inserted == 0
    # 2 locations * 1 modified timestamp = 2 updated
    assert run3.updated == 2
    # 2 locations * 1 unchanged timestamp = 2 skipped
    assert run3.skipped == 2


def test_pipeline_failure_isolation(monkeypatch):
    source_id, loc1_id, loc2_id = _seed_source_and_locations()
    pipeline = IngestionPipeline(session_factory=TestingSessionLocal)

    fetched_at = datetime.now(UTC)
    valid_record = normalize_open_meteo_record(
        location_id=loc1_id,
        source_id=source_id,
        raw_time="2026-10-20T12:00",
        raw_measurements={"temperature_2m": 25.0},
        fetched_at=fetched_at,
    )

    def mock_adapter_run(self, source, targets, http_client, settings):
        target = targets[0]
        res = AdapterResult()
        if target.slug == "mumbai":
            res.fetched_count = 1
            res.records = [valid_record]
        else:
            # Delhi fails
            res.failed_count = 1
            res.errors = [
                TargetError(
                    target_key="delhi",
                    error_code="fetch_timeout",
                    message="Simulated connection timeout for delhi",
                )
            ]
        return res

    monkeypatch.setattr(OpenMeteoAdapter, "run", mock_adapter_run)

    run = pipeline.execute_run(source_id=source_id)
    assert run.status == IngestionStatus.PARTIAL
    assert run.records_fetched == 1
    assert run.inserted == 1
    assert run.failed == 1
    assert run.error_summary is not None
    assert "Simulated connection timeout for delhi" in run.error_summary

    # Verify Mumbai record is intact and committed despite Delhi failure
    with TestingSessionLocal() as db:
        mumbai_records = db.query(WeatherRecord).filter_by(location_id=loc1_id).all()
        assert len(mumbai_records) == 1
        assert mumbai_records[0].temperature_c == 25.0


def test_pipeline_invalid_source_and_missing_adapter():
    pipeline = IngestionPipeline(session_factory=TestingSessionLocal)

    # 1. Non-existent source ID raises ValueError
    with pytest.raises(ValueError, match="DataSource with id 999999 not found"):
        pipeline.execute_run(source_id=999999)

    # 2. Source with unmapped adapter key fails cleanly
    with TestingSessionLocal() as db:
        source = DataSource(
            name="unknown_source",
            display_name="Unknown",
            source_type="weather_api",
            adapter_key="nonexistent_adapter_key",
            trust_level="provider_model",
            is_enabled=True,
            interval_seconds=3600,
            attribution_text="Unknown attribution",
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        bad_source_id = source.id

    run = pipeline.execute_run(source_id=bad_source_id)
    assert run.status == IngestionStatus.FAILED
    assert "No registered adapter found" in run.error_summary
