"""Unit tests for weather ingestion normalizers and validation functions."""

from datetime import UTC, datetime

import pytest

from app.ingestion.normalizers import (
    ValidationErrorItem,
    compute_content_hash,
    normalize_open_meteo_record,
    parse_utc_timestamp,
    validate_range,
)


def test_validate_range_valid_and_null() -> None:
    # Valid float
    assert validate_range(25.456, -90.0, 60.0, "temp") == 25.46
    # Valid int
    assert validate_range(80.2, 0.0, 100.0, "humidity", as_int=True) == 80
    # Null returns None
    assert validate_range(None, 0.0, 100.0, "rain") is None


def test_validate_range_out_of_bounds_and_non_numeric() -> None:
    # Below min
    with pytest.raises(ValidationErrorItem) as exc:
        validate_range(-95.0, -90.0, 60.0, "temperature_c")
    assert "out of bounds" in str(exc.value)

    # Above max (never clamped per PRD line 160)
    with pytest.raises(ValidationErrorItem) as exc:
        validate_range(65.0, -90.0, 60.0, "temperature_c")
    assert "out of bounds" in str(exc.value)

    # Non-numeric
    with pytest.raises(ValidationErrorItem) as exc:
        validate_range("not-a-number", 0.0, 100.0, "wind_speed")
    assert "Non-numeric" in str(exc.value)


def test_parse_utc_timestamp() -> None:
    # Valid UTC ISO string with offset
    dt = parse_utc_timestamp("2026-10-20T12:00:00+00:00")
    assert dt.tzinfo == UTC
    assert dt.hour == 12

    # ISO string without offset (assumes UTC when requested timezone=UTC)
    dt2 = parse_utc_timestamp("2026-10-20T15:30")
    assert dt2.tzinfo == UTC
    assert dt2.hour == 15

    # Already datetime with tzinfo
    dt3 = parse_utc_timestamp(datetime(2026, 10, 20, 8, 0, tzinfo=UTC))
    assert dt3.tzinfo == UTC

    # Naive datetime rejected
    with pytest.raises(ValidationErrorItem):
        parse_utc_timestamp(datetime(2026, 10, 20, 8, 0))

    # Empty string rejected
    with pytest.raises(ValidationErrorItem):
        parse_utc_timestamp("   ")

    # Malformed string rejected
    with pytest.raises(ValidationErrorItem):
        parse_utc_timestamp("invalid-date-format")


def test_compute_content_hash() -> None:
    m1 = {"temperature_c": 25.0, "relative_humidity_pct": 60.0, "wind_speed_kmh": 12.0}
    m2 = {"temperature_c": 25.0, "relative_humidity_pct": 60.0, "wind_speed_kmh": 12.0}
    m3 = {"temperature_c": 26.0, "relative_humidity_pct": 60.0, "wind_speed_kmh": 12.0}

    h1 = compute_content_hash(m1)
    h2 = compute_content_hash(m2)
    h3 = compute_content_hash(m3)

    assert len(h1) == 64
    assert h1 == h2
    assert h1 != h3


def test_normalize_open_meteo_observation_vs_forecast_split() -> None:
    fetched_at = datetime(2026, 10, 20, 14, 25, tzinfo=UTC)
    raw_measurements = {
        "temperature_2m": 28.5,
        "apparent_temperature": 31.0,
        "relative_humidity_2m": 75.0,
        "precipitation": 0.0,
        "rain": 0.0,
        "precipitation_probability": 10,
        "wind_speed_10m": 15.2,
        "wind_gusts_10m": 22.4,
        "wind_direction_10m": 180.0,
    }

    # 1. Past/Current hour (<= 14:00 floor) -> Observation
    obs_record = normalize_open_meteo_record(
        location_id=1,
        source_id=1,
        raw_time="2026-10-20T14:00:00Z",
        raw_measurements=raw_measurements,
        fetched_at=fetched_at,
    )
    assert obs_record.record_kind == "observation"
    assert obs_record.measurement_basis == "model_analysis"
    assert obs_record.issued_at is None
    assert obs_record.temperature_c == 28.5
    assert len(obs_record.content_hash) == 64

    # 2. Future hour (> 14:00 floor) -> Forecast
    forecast_record = normalize_open_meteo_record(
        location_id=1,
        source_id=1,
        raw_time="2026-10-20T15:00:00Z",
        raw_measurements=raw_measurements,
        fetched_at=fetched_at,
    )
    assert forecast_record.record_kind == "forecast"
    assert forecast_record.measurement_basis == "model_forecast"
    assert forecast_record.issued_at == fetched_at
