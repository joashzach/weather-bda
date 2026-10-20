"""Live network test for Open-Meteo ingestion with repeat-run deduplication verification."""

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.enums import IngestionStatus, IngestionTrigger
from app.db.models.data_sources import DataSource
from app.db.models.locations import Location
from app.ingestion.pipeline import IngestionPipeline


@pytest.mark.live
def test_live_open_meteo_ingestion_and_deduplication(db_session: Session) -> None:
    """Execute live Open-Meteo ingestion twice and verify deduplication counts."""
    settings = get_settings()

    # 1. Ensure active location exists
    loc = db_session.query(Location).filter(Location.slug == "bangalore").first()
    if not loc:
        loc = Location(
            name="Bengaluru",
            slug="bangalore",
            region="Karnataka",
            country_code="IN",
            latitude=12.9716,
            longitude=77.5946,
            is_active=True,
        )
        db_session.add(loc)
        db_session.commit()
        db_session.refresh(loc)

    # 2. Ensure open_meteo data source exists and is enabled
    source = db_session.query(DataSource).filter(DataSource.name == "open_meteo").first()
    if not source:
        source = DataSource(
            name="open_meteo",
            display_name="Open-Meteo Weather API",
            source_type="weather_api",
            adapter_key="open_meteo",
            trust_level="provider_model",
            is_enabled=True,
            interval_seconds=3600,
            attribution_text="Weather data by Open-Meteo.com",
            config={"past_days": 1, "forecast_days": 1},
        )
        db_session.add(source)
        db_session.commit()
        db_session.refresh(source)
    else:
        source.is_enabled = True
        source.config = {"past_days": 1, "forecast_days": 1}
        db_session.commit()

    session_factory = sessionmaker(bind=db_session.get_bind())
    pipeline = IngestionPipeline(session_factory=session_factory, settings=settings)

    # 3. First run: manual ingestion against live Open-Meteo
    try:
        run1 = pipeline.execute_run(source_id=source.id, trigger=IngestionTrigger.MANUAL)
    except Exception as exc:
        pytest.fail(f"Live network ingestion failed on Run 1 with unexpected exception: {exc}")

    # Check for network error / DNS failure in run result
    if run1.status == IngestionStatus.FAILED and "connect" in (run1.error_summary or "").lower():
        pytest.skip(f"No network access available to live Open-Meteo: {run1.error_summary}")

    assert run1.status == IngestionStatus.SUCCEEDED, f"Run 1 failed: {run1.error_summary}"
    assert run1.records_fetched > 0, "Run 1 fetched 0 records"
    assert run1.inserted > 0, f"Expected inserted > 0 on fresh run, got {run1.inserted}"
    assert run1.failed == 0, f"Expected 0 failed, got {run1.failed}"

    # 4. Second run: immediate re-run to verify deduplication
    run2 = pipeline.execute_run(source_id=source.id, trigger=IngestionTrigger.MANUAL)

    assert run2.status == IngestionStatus.SUCCEEDED, f"Run 2 failed: {run2.error_summary}"
    assert run2.records_fetched > 0, "Run 2 fetched 0 records"
    # Deduplication guarantee: 0 new rows inserted!
    assert run2.inserted == 0, f"Expected 0 new inserts on repeat run (dedup), got {run2.inserted}"
    assert run2.skipped + run2.updated == run2.records_fetched, (
        f"All records must be skipped or updated on rerun: skipped={run2.skipped}, "
        f"updated={run2.updated}, fetched={run2.records_fetched}"
    )
    assert run2.failed == 0, f"Expected 0 failed on repeat run, got {run2.failed}"

    # Output real telemetry counts for verification report
    print(
        f"\n[LIVE OPEN-METEO TELEMETRY]\n"
        f"Run 1: status={run1.status}, fetched={run1.records_fetched}, "
        f"inserted={run1.inserted}, updated={run1.updated}, skipped={run1.skipped}, failed={run1.failed}\n"
        f"Run 2: status={run2.status}, fetched={run2.records_fetched}, "
        f"inserted={run2.inserted}, updated={run2.updated}, skipped={run2.skipped}, failed={run2.failed}"
    )
