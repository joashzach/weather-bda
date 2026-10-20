"""Integration tests for Locations and Weather REST API endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import MeasurementBasis, RecordKind, TrustLevel
from app.db.models.data_sources import DataSource
from app.db.models.locations import Location
from app.db.models.weather_records import WeatherRecord


def _seed_weather_data(db: Session):
    # Data source
    source = DataSource(
        name="open_meteo",
        display_name="Open-Meteo",
        source_type="weather_api",
        adapter_key="open_meteo",
        trust_level=TrustLevel.PROVIDER_MODEL,
        is_enabled=True,
        interval_seconds=3600,
        attribution_text="Weather data by Open-Meteo under CC BY 4.0",
    )
    db.add(source)
    db.flush()

    # Locations (2 active, 1 inactive)
    loc_active1 = Location(
        slug="mumbai",
        name="Mumbai",
        region="Maharashtra",
        country_code="IN",
        latitude=19.076,
        longitude=72.877,
        is_active=True,
    )
    loc_active2 = Location(
        slug="delhi",
        name="Delhi",
        region="Delhi",
        country_code="IN",
        latitude=28.613,
        longitude=77.209,
        is_active=True,
    )
    loc_inactive = Location(
        slug="old_station",
        name="Old Station",
        region="Inactive Region",
        country_code="IN",
        latitude=10.000,
        longitude=75.000,
        is_active=False,
    )
    db.add_all([loc_active1, loc_active2, loc_inactive])
    db.flush()

    now = datetime.now(UTC)

    # Weather records for Mumbai:
    # 1. Observation 2 hours ago
    rec_obs_past = WeatherRecord(
        location_id=loc_active1.id,
        source_id=source.id,
        record_kind=RecordKind.OBSERVATION,
        valid_at=now - timedelta(hours=2),
        issued_at=None,
        fetched_at=now - timedelta(hours=2),
        content_hash="a" * 64,
        measurement_basis=MeasurementBasis.MODEL_ANALYSIS,
        temperature_c=28.5,
        relative_humidity_pct=75.0,
        wind_speed_kmh=15.0,
    )
    # 2. Observation 1 hour ago (newest observation)
    rec_obs_latest = WeatherRecord(
        location_id=loc_active1.id,
        source_id=source.id,
        record_kind=RecordKind.OBSERVATION,
        valid_at=now - timedelta(hours=1),
        issued_at=None,
        fetched_at=now - timedelta(hours=1),
        content_hash="b" * 64,
        measurement_basis=MeasurementBasis.MODEL_ANALYSIS,
        temperature_c=29.0,
        relative_humidity_pct=72.0,
        wind_speed_kmh=14.0,
    )
    # 3. Forecast 2 hours ahead
    rec_fc_soon = WeatherRecord(
        location_id=loc_active1.id,
        source_id=source.id,
        record_kind=RecordKind.FORECAST,
        valid_at=now + timedelta(hours=2),
        issued_at=now,
        fetched_at=now,
        content_hash="c" * 64,
        measurement_basis=MeasurementBasis.MODEL_FORECAST,
        temperature_c=31.0,
        relative_humidity_pct=65.0,
        wind_speed_kmh=12.0,
    )
    # 4. Forecast 5 hours ahead
    rec_fc_later = WeatherRecord(
        location_id=loc_active1.id,
        source_id=source.id,
        record_kind=RecordKind.FORECAST,
        valid_at=now + timedelta(hours=5),
        issued_at=now,
        fetched_at=now,
        content_hash="d" * 64,
        measurement_basis=MeasurementBasis.MODEL_FORECAST,
        temperature_c=33.0,
        relative_humidity_pct=60.0,
        wind_speed_kmh=10.0,
    )

    db.add_all([rec_obs_past, rec_obs_latest, rec_fc_soon, rec_fc_later])
    db.commit()

    return {
        "source": source,
        "loc1": loc_active1,
        "loc2": loc_active2,
        "loc_inactive": loc_inactive,
        "rec_obs_latest": rec_obs_latest,
        "rec_fc_soon": rec_fc_soon,
    }


def test_get_locations(client: TestClient, db_session: Session):
    _seed_weather_data(db_session)

    resp = client.get("/api/v1/locations")
    assert resp.status_code == 200
    res_data = resp.json()
    items = res_data["items"]
    assert len(items) == 2

    slugs = [loc["slug"] for loc in items]
    assert "mumbai" in slugs
    assert "delhi" in slugs
    assert "old_station" not in slugs  # Inactive location must be excluded


def test_list_weather_records_default_and_filters(client: TestClient, db_session: Session):
    data = _seed_weather_data(db_session)
    loc1 = data["loc1"]

    # 1. Default request (observations within past 24 hours)
    resp = client.get("/api/v1/weather")
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["total"] == 2
    for item in res_data["items"]:
        assert item["kind"] == "observation"
        assert item["location"]["slug"] == "mumbai"

    # 2. Filter by location_id
    resp = client.get(f"/api/v1/weather?location_id={loc1.id}")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2

    # 3. Filter by non-existent location_id -> 404
    resp = client.get("/api/v1/weather?location_id=999999")
    assert resp.status_code == 404
    err = resp.json()["error"]
    assert err["code"] == "not_found"

    # 4. Filter by kind="forecast"
    resp = client.get(f"/api/v1/weather?location_id={loc1.id}&kind=forecast")
    assert resp.status_code == 200
    fc_data = resp.json()
    assert fc_data["total"] == 2
    for item in fc_data["items"]:
        assert item["kind"] == "forecast"

    # 5. Filter by kind="all"
    resp = client.get(f"/api/v1/weather?location_id={loc1.id}&kind=all")
    assert resp.status_code == 200
    assert resp.json()["total"] == 4

    # 6. Filter by source name
    resp = client.get("/api/v1/weather?source=open_meteo")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_list_weather_sorting_and_pagination(client: TestClient, db_session: Session):
    data = _seed_weather_data(db_session)
    loc1 = data["loc1"]

    # 1. Ascending sort by valid_at
    resp = client.get(f"/api/v1/weather?location_id={loc1.id}&kind=all&sort=valid_at")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 4
    timestamps = [it["valid_at"] for it in items]
    assert timestamps == sorted(timestamps)

    # 2. Descending sort by valid_at
    resp = client.get(f"/api/v1/weather?location_id={loc1.id}&kind=all&sort=-valid_at")
    assert resp.status_code == 200
    items = resp.json()["items"]
    timestamps = [it["valid_at"] for it in items]
    assert timestamps == sorted(timestamps, reverse=True)

    # 3. Invalid sort field -> 422
    resp = client.get("/api/v1/weather?sort=temperature")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"

    # 4. Pagination: limit=2, offset=0
    resp = client.get(f"/api/v1/weather?location_id={loc1.id}&kind=all&limit=2&offset=0")
    assert resp.status_code == 200
    page1 = resp.json()
    assert len(page1["items"]) == 2
    assert page1["total"] == 4

    # Pagination: limit=2, offset=2
    resp = client.get(f"/api/v1/weather?location_id={loc1.id}&kind=all&limit=2&offset=2")
    assert resp.status_code == 200
    page2 = resp.json()
    assert len(page2["items"]) == 2
    assert page2["items"][0]["id"] != page1["items"][0]["id"]


def test_list_weather_date_range_validations(client: TestClient, db_session: Session):
    _seed_weather_data(db_session)
    now = datetime.now(UTC)

    # 1. Valid range with Z suffix
    from_iso = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = client.get(f"/api/v1/weather?from={from_iso}&to={to_iso}&kind=all")
    assert resp.status_code == 200

    # 2. Naive ISO timestamp (no timezone offset) -> 422
    resp = client.get("/api/v1/weather?from=2026-10-20T10:00:00")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"

    # 3. from >= to -> 422
    resp = client.get(f"/api/v1/weather?from={to_iso}&to={from_iso}")
    assert resp.status_code == 422
    assert "earlier" in resp.json()["error"]["message"]

    # 4. Span > 31 days -> 422
    old_from = (now - timedelta(days=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = client.get(f"/api/v1/weather?from={old_from}&to={to_iso}")
    assert resp.status_code == 422
    assert "31 days" in resp.json()["error"]["message"]


def test_get_latest_weather(client: TestClient, db_session: Session):
    data = _seed_weather_data(db_session)
    loc1 = data["loc1"]
    loc2 = data["loc2"]
    latest_rec = data["rec_obs_latest"]
    earliest_fc = data["rec_fc_soon"]

    # 1. Latest observation across all active locations
    resp = client.get("/api/v1/weather/latest?kind=observation")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == latest_rec.id
    # loc2 (Delhi) has no observations, so loc2.id should be in missing_location_ids
    assert loc2.id in body["missing_location_ids"]

    # 2. Latest forecast across all active locations
    resp = client.get("/api/v1/weather/latest?kind=forecast")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == earliest_fc.id

    # 3. Filter by single location_id
    resp = client.get(f"/api/v1/weather/latest?location_id={loc1.id}&kind=observation")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["missing_location_ids"] == []

    # 4. Filter by location without records
    resp = client.get(f"/api/v1/weather/latest?location_id={loc2.id}&kind=observation")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 0
    assert body["missing_location_ids"] == [loc2.id]

    # 5. Non-existent location -> 404
    resp = client.get("/api/v1/weather/latest?location_id=999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"

    # 6. Invalid kind -> 422
    resp = client.get("/api/v1/weather/latest?kind=invalid_kind")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_get_weather_by_id(client: TestClient, db_session: Session):
    data = _seed_weather_data(db_session)
    latest_rec = data["rec_obs_latest"]

    # 1. Valid ID -> 200 with full structure
    resp = client.get(f"/api/v1/weather/{latest_rec.id}")
    assert resp.status_code == 200
    item = resp.json()
    assert item["id"] == latest_rec.id
    assert item["kind"] == "observation"
    assert item["location"]["slug"] == "mumbai"
    assert item["source"]["name"] == "open_meteo"
    assert item["source"]["attribution_text"] == "Weather data by Open-Meteo under CC BY 4.0"
    assert item["measurements"]["temperature_c"] == 29.0
    assert item["measurements"]["relative_humidity_pct"] == 72.0
    assert item["measurements"]["wind_speed_kmh"] == 14.0

    # 2. Non-existent ID -> 404
    resp = client.get("/api/v1/weather/999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
