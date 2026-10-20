"""Unit tests for Open-Meteo adapter, retries, validation, and sanitization."""

from unittest.mock import MagicMock

import httpx

from app.core.config import Settings
from app.db.models.data_sources import DataSource
from app.db.models.locations import Location
from app.ingestion.adapters.open_meteo import OpenMeteoAdapter, sanitize_error_message


def test_sanitize_error_message():
    # Strips query params
    msg = "Request to https://api.open-meteo.com/v1/forecast?latitude=19.07&secret=123 failed"
    sanitized = sanitize_error_message(msg)
    assert "?secret=123" not in sanitized
    assert "[QUERY STRIPPED]" in sanitized

    # Truncates to 1000 chars
    long_msg = "X" * 1500
    assert len(sanitize_error_message(long_msg)) == 1000


def test_is_configured():
    adapter = OpenMeteoAdapter()
    source = DataSource(name="open_meteo", adapter_key="open_meteo")

    # Valid config
    valid_settings = Settings(
        OPEN_METEO_BASE_URL="https://api.open-meteo.com/v1/forecast",
        ALLOWED_SOURCE_HOSTS="api.open-meteo.com,localhost",
    )
    assert adapter.is_configured(source, valid_settings) is True

    # Empty base URL
    empty_settings = Settings(OPEN_METEO_BASE_URL="", ALLOWED_SOURCE_HOSTS="api.open-meteo.com")
    assert adapter.is_configured(source, empty_settings) is False

    # Host not in allowed list
    unallowed_settings = Settings(
        OPEN_METEO_BASE_URL="https://malicious.org/forecast",
        ALLOWED_SOURCE_HOSTS="api.open-meteo.com",
    )
    assert adapter.is_configured(source, unallowed_settings) is False


def test_adapter_successful_run():
    adapter = OpenMeteoAdapter()
    source = DataSource(id=1, name="open_meteo", adapter_key="open_meteo", config={})
    location = Location(
        id=10,
        slug="mumbai",
        name="Mumbai",
        latitude=19.076,
        longitude=72.877,
        is_active=True,
    )

    settings = Settings(HTTP_MAX_RETRIES=2)
    mock_http = MagicMock()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
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
    mock_http.get.return_value = mock_resp

    result = adapter.run(
        source=source,
        targets=[location],
        http_client=mock_http,
        settings=settings,
    )

    assert result.fetched_count == 2
    assert result.failed_count == 0
    assert len(result.records) == 2
    assert len(result.errors) == 0

    rec = result.records[0]
    assert rec.location_id == 10
    assert rec.source_id == 1
    assert rec.temperature_c == 28.5
    assert rec.precipitation_probability_pct == 10


def test_adapter_array_mismatch():
    adapter = OpenMeteoAdapter()
    source = DataSource(id=1, name="open_meteo", adapter_key="open_meteo", config={})
    location = Location(
        id=10,
        slug="mumbai",
        name="Mumbai",
        latitude=19.076,
        longitude=72.877,
        is_active=True,
    )

    settings = Settings(HTTP_MAX_RETRIES=2)
    mock_http = MagicMock()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "hourly": {
            "time": ["2026-10-20T10:00", "2026-10-20T11:00"],
            "temperature_2m": [28.5],  # Mismatched length (1 instead of 2)
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
    mock_http.get.return_value = mock_resp

    result = adapter.run(
        source=source,
        targets=[location],
        http_client=mock_http,
        settings=settings,
    )

    assert result.fetched_count == 0
    assert result.failed_count == 2
    assert len(result.errors) == 1
    assert result.errors[0].error_code == "length_mismatch"
    assert "temperature_2m" in result.errors[0].message


def test_adapter_empty_timestamps():
    adapter = OpenMeteoAdapter()
    source = DataSource(id=1, name="open_meteo", adapter_key="open_meteo")
    location = Location(id=10, slug="mumbai", latitude=19.0, longitude=72.0)

    settings = Settings(HTTP_MAX_RETRIES=2)
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"hourly": {"time": []}}
    mock_http.get.return_value = mock_resp

    result = adapter.run(
        source=source, targets=[location], http_client=mock_http, settings=settings
    )
    assert result.failed_count == 1
    assert result.errors[0].error_code == "empty_data"


def test_adapter_retries_on_500_and_captures_error():
    adapter = OpenMeteoAdapter()
    source = DataSource(id=1, name="open_meteo", adapter_key="open_meteo")
    location = Location(id=10, slug="delhi", latitude=28.6, longitude=77.2)

    # Use HTTP_MAX_RETRIES=2 and fast retry
    settings = Settings(HTTP_MAX_RETRIES=2)
    mock_http = MagicMock()

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_http.get.return_value = mock_resp

    result = adapter.run(
        source=source, targets=[location], http_client=mock_http, settings=settings
    )

    assert result.failed_count == 1
    assert len(result.errors) == 1
    assert result.errors[0].error_code == "fetch_error"
    assert "HTTP 500" in result.errors[0].message
    # Assert tenacity retried exactly HTTP_MAX_RETRIES times
    assert mock_http.get.call_count == 2


def test_adapter_retries_on_timeout():
    adapter = OpenMeteoAdapter()
    source = DataSource(id=1, name="open_meteo", adapter_key="open_meteo")
    location = Location(id=10, slug="delhi", latitude=28.6, longitude=77.2)

    settings = Settings(HTTP_MAX_RETRIES=2)
    mock_http = MagicMock()
    mock_http.get.side_effect = httpx.ConnectTimeout("Connection timed out")

    result = adapter.run(
        source=source, targets=[location], http_client=mock_http, settings=settings
    )

    assert result.failed_count == 1
    assert result.errors[0].error_code == "fetch_error"
    assert "Connection timed out" in result.errors[0].message
    assert mock_http.get.call_count == 2


def test_adapter_skips_invalid_record_but_keeps_valid():
    adapter = OpenMeteoAdapter()
    source = DataSource(id=1, name="open_meteo", adapter_key="open_meteo")
    location = Location(id=10, slug="delhi", latitude=28.6, longitude=77.2)

    settings = Settings(HTTP_MAX_RETRIES=1)
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "hourly": {
            "time": ["2026-10-20T10:00", "2026-10-20T11:00"],
            "temperature_2m": [25.0, 150.0],  # 150.0°C exceeds normalizer range (-90..60)
            "apparent_temperature": [25.0, 25.0],
            "relative_humidity_2m": [50.0, 50.0],
            "precipitation": [0.0, 0.0],
            "rain": [0.0, 0.0],
            "precipitation_probability": [0, 0],
            "wind_speed_10m": [10.0, 10.0],
            "wind_gusts_10m": [15.0, 15.0],
            "wind_direction_10m": [180.0, 180.0],
        }
    }
    mock_http.get.return_value = mock_resp

    result = adapter.run(
        source=source, targets=[location], http_client=mock_http, settings=settings
    )
    assert result.fetched_count == 2
    assert result.failed_count == 1
    assert len(result.records) == 1
    assert result.records[0].temperature_c == 25.0
