"""Unit tests for data.gov.in Open Data portal adapter conforming to PRD Section 8.4."""

from unittest.mock import MagicMock

from app.core.config import Settings
from app.db.models.data_sources import DataSource
from app.db.models.locations import Location
from app.ingestion.adapters.data_gov_in import DataGovInAdapter

SAMPLE_DATA_GOV_IN_JSON = {
    "status": "ok",
    "total": 3,
    "count": 3,
    "limit": "100",
    "offset": "0",
    "records": [
        {
            "station": "DELHI SAFDARJUNG",
            "timestamp": "2026-10-20T10:00:00Z",
            "temperature_k": "298.15",  # 25.0 C
            "relative_humidity": "65",
            "rainfall": "0.0",
            "wind_speed": "14.5",
        },
        {
            "station": "MUMBAI SANTACRUZ",
            "timestamp": "2026-10-20T10:00:00Z",
            "temperature_k": "304.15",  # 31.0 C
            "relative_humidity": "78",
            "rainfall": "12.4",
            "wind_speed": "22.0",
        },
        {
            "station": "UNKNOWN REMOTE VILLAGE",
            "timestamp": "2026-10-20T10:00:00Z",
            "temperature_k": "295.0",
            "relative_humidity": "50",
        },
    ],
}


def test_data_gov_in_is_configured():
    adapter = DataGovInAdapter()

    # 1. Missing API key in settings
    settings_no_key = Settings(DATA_GOV_IN_API_KEY="")
    s1 = DataSource(name="dg1", config={"resource_id": "res-12345"})
    assert adapter.is_configured(s1, settings_no_key) is False

    # 2. Missing resource_id in source config
    settings_with_key = Settings(DATA_GOV_IN_API_KEY="test_api_key_12345")
    s2 = DataSource(name="dg2", config={})
    assert adapter.is_configured(s2, settings_with_key) is False

    # 3. Valid configuration
    s3 = DataSource(name="dg3", config={"resource_id": "res-12345"})
    assert adapter.is_configured(s3, settings_with_key) is True


def test_data_gov_in_run_unconfigured_fails():
    adapter = DataGovInAdapter()
    settings = Settings(DATA_GOV_IN_API_KEY="")
    source = DataSource(name="dg", config={"resource_id": "res-12345"})
    mock_client = MagicMock()

    res = adapter.run(source, targets=[], http_client=mock_client, settings=settings)
    assert res.failed_count == 1
    assert res.errors[0].error_code == "source_not_configured"


def test_data_gov_in_schema_mapping_and_station_matching():
    adapter = DataGovInAdapter()
    settings = Settings(DATA_GOV_IN_API_KEY="secret_key")

    delhi = Location(id=1, slug="delhi")
    mumbai = Location(id=2, slug="mumbai")
    targets = [delhi, mumbai]

    source = DataSource(
        id=5,
        name="data_gov_in_weather",
        config={
            "resource_id": "95914e62-weather-realtime",
            "field_map": {
                "station_name": "station",
                "valid_at": "timestamp",
                "temperature_c": "temperature_k",
                "relative_humidity_pct": "relative_humidity",
                "precipitation_mm": "rainfall",
                "wind_speed_kmh": "wind_speed",
            },
            "unit_conversions": {
                "temperature_c": "kelvin_to_celsius",
            },
            "location_match": {
                "delhi safdarjung": "delhi",
                "mumbai santacruz": "mumbai",
            },
            "measurement_basis": "station",
        },
    )

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = SAMPLE_DATA_GOV_IN_JSON
    mock_resp.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_resp

    res = adapter.run(source, targets=targets, http_client=mock_client, settings=settings)

    assert res.failed_count == 0
    # 2 matched records (Delhi, Mumbai); 1 unmatched record skipped
    assert len(res.records) == 2

    # Check Delhi record
    r_delhi = next(r for r in res.records if r.location_id == delhi.id)
    assert r_delhi.record_kind == "observation"
    assert r_delhi.measurement_basis == "station"
    assert r_delhi.temperature_c == 25.0  # 298.15 K -> 25.0 C
    assert r_delhi.relative_humidity_pct == 65.0
    assert r_delhi.precipitation_mm == 0.0
    assert r_delhi.wind_speed_kmh == 14.5
    assert len(r_delhi.content_hash) == 64

    # Check Mumbai record
    r_mumbai = next(r for r in res.records if r.location_id == mumbai.id)
    assert r_mumbai.temperature_c == 31.0  # 304.15 K -> 31.0 C
    assert r_mumbai.precipitation_mm == 12.4
    assert r_mumbai.relative_humidity_pct == 78.0
