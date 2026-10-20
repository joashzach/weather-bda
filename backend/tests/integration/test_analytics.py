"""Integration tests for Analytics REST API endpoints conforming to PRD Section 9."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user
from app.core.enums import MeasurementBasis, RecordKind, TrustLevel, UserRole
from app.db.models.citizen_reports import CitizenReport
from app.db.models.data_sources import DataSource
from app.db.models.ingestion_runs import IngestionRun
from app.db.models.locations import Location
from app.db.models.users import User
from app.db.models.weather_records import WeatherRecord
from app.main import app
from tests.conftest import test_engine


@pytest.fixture(autouse=True)
def clean_database(setup_test_db):
    """Clean tables before and after each test."""

    def _do_clean():
        with test_engine.begin() as conn:
            conn.execute(text("DELETE FROM weather_records"))
            conn.execute(text("DELETE FROM ingestion_runs"))
            conn.execute(text("DELETE FROM citizen_reports"))
            conn.execute(text("DELETE FROM locations"))
            conn.execute(text("DELETE FROM data_sources"))

    _do_clean()
    yield
    _do_clean()


def _seed_analytics_fixture(db: Session):
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)

    # 1. Locations
    mumbai = Location(
        slug="mumbai",
        name="Mumbai",
        region="Maharashtra",
        country_code="IN",
        latitude=19.076,
        longitude=72.877,
        is_active=True,
    )
    delhi = Location(
        slug="delhi",
        name="Delhi",
        region="Delhi",
        country_code="IN",
        latitude=28.613,
        longitude=77.209,
        is_active=True,
    )
    inactive_loc = Location(
        slug="closed_station",
        name="Closed Station",
        region="Remote",
        country_code="IN",
        latitude=15.0,
        longitude=75.0,
        is_active=False,
    )
    db.add_all([mumbai, delhi, inactive_loc])
    db.flush()

    # 2. Data Sources
    source_active = DataSource(
        name="open_meteo",
        display_name="Open-Meteo",
        source_type="weather_api",
        adapter_key="open_meteo",
        trust_level=TrustLevel.PROVIDER_MODEL,
        is_enabled=True,
        interval_seconds=3600,
        attribution_text="Weather data by Open-Meteo under CC BY 4.0",
        last_success_at=now - timedelta(minutes=15),  # fresh (diff <= 7200s)
    )
    source_disabled = DataSource(
        name="citizen_reports",
        display_name="Citizen Reports",
        source_type="citizen",
        adapter_key="citizen",
        trust_level=TrustLevel.CITIZEN,
        is_enabled=False,
        interval_seconds=3600,
        attribution_text="Citizen weather reports",
    )
    db.add_all([source_active, source_disabled])
    db.flush()

    # 3. Weather Records: 24 hourly observations for Mumbai
    # Temperatures: 20.0 to 31.5 (mean = 25.75, min = 20.0, max = 31.5)
    records = []
    base_time = now - timedelta(days=2)
    for i in range(24):
        valid = base_time + timedelta(hours=i)
        temp = 20.0 + (i * 0.5)
        precip = 1.0 if i % 4 == 0 else 0.0
        records.append(
            WeatherRecord(
                location_id=mumbai.id,
                source_id=source_active.id,
                record_kind=RecordKind.OBSERVATION,
                valid_at=valid,
                issued_at=None,
                fetched_at=valid,
                content_hash=f"mum_{i:02d}" + "0" * 58,
                measurement_basis=MeasurementBasis.MODEL_ANALYSIS,
                temperature_c=temp,
                relative_humidity_pct=60.0,
                precipitation_mm=precip,
                wind_speed_kmh=10.0 + (i * 0.2),
                wind_gust_kmh=15.0 + (i * 0.3),
            )
        )

    # 24 hourly observations for Delhi
    # Temperatures: 10.0 to 21.5 (mean = 15.75, min = 10.0, max = 21.5)
    for i in range(24):
        valid = base_time + timedelta(hours=i)
        temp = 10.0 + (i * 0.5)
        records.append(
            WeatherRecord(
                location_id=delhi.id,
                source_id=source_active.id,
                record_kind=RecordKind.OBSERVATION,
                valid_at=valid,
                issued_at=None,
                fetched_at=valid,
                content_hash=f"del_{i:02d}" + "0" * 58,
                measurement_basis=MeasurementBasis.MODEL_ANALYSIS,
                temperature_c=temp,
                relative_humidity_pct=50.0,
                precipitation_mm=0.0,
                wind_speed_kmh=12.0,
                wind_gust_kmh=18.0,
            )
        )

    # 5 Forecast records for Mumbai tomorrow (must never pollute observation aggregates)
    for i in range(5):
        valid = now + timedelta(hours=i + 1)
        records.append(
            WeatherRecord(
                location_id=mumbai.id,
                source_id=source_active.id,
                record_kind=RecordKind.FORECAST,
                valid_at=valid,
                issued_at=now,
                fetched_at=now,
                content_hash=f"fc_{i:02d}" + "0" * 59,
                measurement_basis=MeasurementBasis.MODEL_FORECAST,
                temperature_c=35.0,
                relative_humidity_pct=40.0,
            )
        )

    db.add_all(records)

    # 4. Citizen Reports (1 verified, 1 pending, 1 rejected)
    rep_verified = CitizenReport(
        event_type="heavy_rain",
        severity="high",
        description="Severe waterlogging on Western Express Highway",
        location_name="Mumbai WEH",
        latitude=19.080,
        longitude=72.880,
        location_id=mumbai.id,
        event_time=now - timedelta(days=1),
        status="verified",
        reviewed_at=now - timedelta(hours=20),
        tracking_token_hash="tok_ver_" + "0" * 56,
        row_version=2,
    )
    rep_pending = CitizenReport(
        event_type="flood",
        severity="moderate",
        description="Knee deep water near station",
        location_name="Delhi Station",
        latitude=28.620,
        longitude=77.210,
        location_id=delhi.id,
        event_time=now - timedelta(hours=12),
        status="pending",
        reviewed_at=None,
        tracking_token_hash="tok_pen_" + "0" * 56,
        row_version=1,
    )
    rep_rejected = CitizenReport(
        event_type="storm",
        severity="low",
        description="False alarm storm",
        location_name="Mumbai South",
        latitude=18.950,
        longitude=72.820,
        location_id=mumbai.id,
        event_time=now - timedelta(hours=6),
        status="rejected",
        reviewed_at=now - timedelta(hours=5),
        tracking_token_hash="tok_rej_" + "0" * 56,
        row_version=2,
    )
    db.add_all([rep_verified, rep_pending, rep_rejected])

    # 5. Ingestion Runs
    run_succ = IngestionRun(
        source_id=source_active.id,
        trigger="scheduled",
        status="succeeded",
        queued_at=now - timedelta(hours=2),
        started_at=now - timedelta(hours=2),
        finished_at=now - timedelta(hours=2) + timedelta(seconds=15),
        records_fetched=48,
        inserted=48,
    )
    run_fail = IngestionRun(
        source_id=source_active.id,
        trigger="scheduled",
        status="failed",
        queued_at=now - timedelta(hours=1),
        started_at=now - timedelta(hours=1),
        finished_at=now - timedelta(hours=1) + timedelta(seconds=5),
        records_fetched=0,
        failed=1,
        error_summary="Connection timeout",
    )
    db.add_all([run_succ, run_fail])

    db.commit()
    return {
        "mumbai": mumbai,
        "delhi": delhi,
        "inactive_loc": inactive_loc,
        "now": now,
        "base_time": base_time,
    }


def test_analytics_summary_anonymous(client: TestClient, db_session: Session):
    data = _seed_analytics_fixture(db_session)
    now = data["now"]
    from_iso = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    resp = client.get(f"/api/v1/analytics/summary?from={from_iso}&to={to_iso}")
    assert resp.status_code == 200
    res = resp.json()

    # Weather checks
    weather = res["weather"]
    assert weather["record_counts"]["observation"] == 48
    assert weather["record_counts"]["forecast"] == 5
    assert weather["locations_with_data"] == 2
    # Temperature: overall min is 10.0 (Delhi), overall max is 31.5 (Mumbai)
    # mean_of_location_means is (25.75 + 15.75) / 2 = 20.75
    assert weather["temperature_c"]["min"] == 10.0
    assert weather["temperature_c"]["max"] == 31.5
    assert weather["temperature_c"]["mean_of_location_means"] == pytest.approx(20.75, abs=0.01)

    # Anonymous Reports: only verified reports are visible
    reports = res["reports"]
    assert reports["total"] == 1
    assert "verified" in reports["by_status"]
    assert "pending" not in reports["by_status"]
    assert "rejected" not in reports["by_status"]

    # Sources Freshness
    sources = {s["name"]: s for s in res["sources"]}
    assert sources["open_meteo"]["freshness"] == "fresh"
    assert sources["citizen_reports"]["freshness"] == "disabled"

    # Ingestion: must be null for anonymous caller
    assert res["ingestion"] is None


def test_analytics_summary_reviewer_and_admin_views(client: TestClient, db_session: Session):
    from app.core.security import create_access_token, hash_password

    data = _seed_analytics_fixture(db_session)
    now = data["now"]
    from_iso = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Create real database-backed reviewer and admin users
    reviewer = User(
        email="rev_analytics@example.com",
        display_name="Reviewer Analytics",
        role=UserRole.REVIEWER,
        password_hash=hash_password("ReviewerPass123!"),
        is_active=True,
        token_version=0,
    )
    admin = User(
        email="admin_analytics@example.com",
        display_name="Admin Analytics",
        role=UserRole.ADMIN,
        password_hash=hash_password("AdminPass123!"),
        is_active=True,
        token_version=0,
    )
    db_session.add_all([reviewer, admin])
    db_session.commit()
    db_session.refresh(reviewer)
    db_session.refresh(admin)

    reviewer_token = create_access_token(user_id=reviewer.id, role=reviewer.role, token_version=0)
    admin_token = create_access_token(user_id=admin.id, role=admin.role, token_version=0)

    # 2. Test Reviewer Role with real Bearer token: sees all report statuses, ingestion is None
    resp = client.get(
        f"/api/v1/analytics/summary?from={from_iso}&to={to_iso}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 200
    res = resp.json()
    assert res["reports"]["total"] == 3
    assert res["reports"]["by_status"]["verified"] == 1
    assert res["reports"]["by_status"]["pending"] == 1
    assert res["reports"]["by_status"]["rejected"] == 1
    assert res["ingestion"] is None

    # 3. Test Admin Role with real Bearer token: sees all report statuses AND ingestion stats
    resp2 = client.get(
        f"/api/v1/analytics/summary?from={from_iso}&to={to_iso}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp2.status_code == 200
    res2 = resp2.json()
    assert res2["reports"]["total"] == 3
    assert res2["ingestion"] is not None
    assert res2["ingestion"]["runs_by_status"]["succeeded"] == 1
    assert res2["ingestion"]["runs_by_status"]["failed"] == 1
    assert res2["ingestion"]["success_rate"] == 0.5
    assert res2["ingestion"]["last_failure_at"] is not None


def test_analytics_timeseries_hourly_and_gap_fill(client: TestClient, db_session: Session):
    data = _seed_analytics_fixture(db_session)
    mumbai = data["mumbai"]
    base_time = data["base_time"]
    from_iso = base_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = (base_time + timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Hourly temperature average
    url = f"/api/v1/analytics/timeseries?location_id={mumbai.id}&metric=temperature_c&from={from_iso}&to={to_iso}&interval=hour&agg=avg"
    resp = client.get(url)
    assert resp.status_code == 200
    res = resp.json()
    assert res["metric"] == "temperature_c"
    assert res["unit"] == "°C"
    assert res["location"]["slug"] == "mumbai"
    assert len(res["buckets"]) == 24
    assert res["buckets"][0]["value"] == 20.0
    assert res["buckets"][1]["value"] == 20.5

    # 2. Hourly precipitation sum
    precip_url = f"/api/v1/analytics/timeseries?location_id={mumbai.id}&metric=precipitation_mm&from={from_iso}&to={to_iso}&interval=hour&agg=sum"
    p_resp = client.get(precip_url)
    assert p_resp.status_code == 200
    p_res = p_resp.json()
    assert p_res["agg"] == "sum"

    # 3. Aggregation 'sum' on temperature_c must be rejected with 422
    bad_agg_url = f"/api/v1/analytics/timeseries?location_id={mumbai.id}&metric=temperature_c&from={from_iso}&to={to_iso}&interval=hour&agg=sum"
    bad_resp = client.get(bad_agg_url)
    assert bad_resp.status_code == 422
    assert "precipitation_mm" in bad_resp.json()["error"]["message"]

    # 4. fill_gaps=True when querying span wider than records
    wide_to_iso = (base_time + timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fill_url = f"/api/v1/analytics/timeseries?location_id={mumbai.id}&metric=temperature_c&from={from_iso}&to={wide_to_iso}&interval=hour&fill_gaps=true"
    fill_resp = client.get(fill_url)
    assert fill_resp.status_code == 200
    fill_buckets = fill_resp.json()["buckets"]
    assert len(fill_buckets) == 31  # 0 to 30 inclusive
    # Last bucket should be empty with value None and sample_count 0
    assert fill_buckets[-1]["value"] is None
    assert fill_buckets[-1]["sample_count"] == 0

    # 5. include_trend=True returns OLS slope
    trend_url = f"/api/v1/analytics/timeseries?location_id={mumbai.id}&metric=temperature_c&from={from_iso}&to={to_iso}&interval=hour&include_trend=true"
    t_resp = client.get(trend_url)
    assert t_resp.status_code == 200
    t_res = t_resp.json()
    assert t_res["trend"] is not None
    assert t_res["trend"]["method"] == "ols"
    assert t_res["trend"]["n"] == 24
    assert t_res["trend"]["slope_per_day"] > 0


def test_analytics_timeseries_validations(client: TestClient, db_session: Session):
    data = _seed_analytics_fixture(db_session)
    mumbai = data["mumbai"]
    now = data["now"]
    from_iso = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Non-existent location -> 404
    resp = client.get(
        f"/api/v1/analytics/timeseries?location_id=999999&metric=temperature_c&from={from_iso}&to={to_iso}"
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"

    # 2. Invalid metric -> 422
    resp = client.get(
        f"/api/v1/analytics/timeseries?location_id={mumbai.id}&metric=fake_metric&from={from_iso}&to={to_iso}"
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"

    # 3. More than 2000 buckets -> 422 (span of 100 days with hour interval = 2400 buckets)
    hundred_days_from = (now - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = client.get(
        f"/api/v1/analytics/timeseries?location_id={mumbai.id}&metric=temperature_c&from={hundred_days_from}&to={to_iso}&interval=hour"
    )
    assert resp.status_code == 422
    assert "2000" in resp.json()["error"]["message"]


def test_analytics_locations(client: TestClient, db_session: Session):
    data = _seed_analytics_fixture(db_session)
    now = data["now"]
    from_iso = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    resp = client.get(f"/api/v1/analytics/locations?from={from_iso}&to={to_iso}&sort=name")
    assert resp.status_code == 200
    res = resp.json()
    assert res["total"] == 2  # Inactive location excluded
    slugs = [it["location"]["slug"] for it in res["items"]]
    assert slugs == ["delhi", "mumbai"]

    mumbai_item = next(it for it in res["items"] if it["location"]["slug"] == "mumbai")
    assert mumbai_item["record_count"] == 24
    assert mumbai_item["coverage_pct"] > 0
    assert mumbai_item["total_precipitation_mm"] == pytest.approx(6.0, abs=0.1)

    # Anonymous sees verified report count only
    assert "verified" in mumbai_item["report_counts"]
    assert "pending" not in mumbai_item["report_counts"]


def test_analytics_events_grouping_and_permissions(client: TestClient, db_session: Session):
    data = _seed_analytics_fixture(db_session)
    now = data["now"]
    from_iso = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Anonymous grouping by event_type (only verified report counted: heavy_rain)
    resp = client.get(f"/api/v1/analytics/events?from={from_iso}&to={to_iso}&group_by=event_type")
    assert resp.status_code == 200
    res = resp.json()
    assert res["totals"]["verified"] == 1
    assert res["totals"]["pending"] is None
    assert len(res["items"]) == 1
    assert res["items"][0]["key"] == "heavy_rain"
    assert res["items"][0]["count"] == 1

    # 2. Anonymous attempting to query status=pending -> 403
    forbidden_resp = client.get(
        f"/api/v1/analytics/events?from={from_iso}&to={to_iso}&status=pending"
    )
    assert forbidden_resp.status_code == 403
    assert forbidden_resp.json()["error"]["code"] == "forbidden"

    # 3. Staff caller grouping by status
    reviewer = User(
        email="rev@example.com",
        display_name="Reviewer",
        role=UserRole.REVIEWER,
        password_hash="dummy",
    )
    app.dependency_overrides[get_optional_current_user] = lambda: reviewer
    try:
        resp_staff = client.get(
            f"/api/v1/analytics/events?from={from_iso}&to={to_iso}&group_by=status"
        )
        assert resp_staff.status_code == 200
        res_staff = resp_staff.json()
        assert res_staff["totals"]["verified"] == 1
        assert res_staff["totals"]["pending"] == 1
        assert res_staff["totals"]["rejected"] == 1
        status_keys = {it["key"] for it in res_staff["items"]}
        assert "verified" in status_keys
        assert "pending" in status_keys
        assert "rejected" in status_keys
    finally:
        app.dependency_overrides.pop(get_optional_current_user, None)


def test_analytics_anomalies_endpoint(client: TestClient, db_session: Session):
    data = _seed_analytics_fixture(db_session)
    mumbai = data["mumbai"]
    now = data["now"]
    source = db_session.query(DataSource).filter_by(name="open_meteo").one()

    # Seed 170 baseline observations for Mumbai (at 25.0 +- 0.5 C)
    baseline_records = []
    base_start = now - timedelta(days=20)
    for i in range(170):
        t = base_start + timedelta(hours=i)
        baseline_records.append(
            WeatherRecord(
                location_id=mumbai.id,
                source_id=source.id,
                record_kind=RecordKind.OBSERVATION,
                valid_at=t,
                issued_at=None,
                fetched_at=t,
                content_hash=f"anom_base_{i:03d}".ljust(64, "0"),
                measurement_basis=MeasurementBasis.MODEL_ANALYSIS,
                temperature_c=25.0 + (0.5 if i % 2 == 0 else -0.5),
            )
        )

    # Seed 1 extreme anomaly observation in evaluation window
    eval_time = now - timedelta(hours=2)
    baseline_records.append(
        WeatherRecord(
            location_id=mumbai.id,
            source_id=source.id,
            record_kind=RecordKind.OBSERVATION,
            valid_at=eval_time,
            issued_at=None,
            fetched_at=eval_time,
            content_hash="anom_eval_01" + "0" * 52,
            measurement_basis=MeasurementBasis.MODEL_ANALYSIS,
            temperature_c=48.0,  # Extreme heat outlier
        )
    )
    db_session.add_all(baseline_records)
    db_session.commit()

    from_iso = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    url = f"/api/v1/analytics/anomalies?location_id={mumbai.id}&metric=temperature_c&from={from_iso}&to={to_iso}&baseline_days=25&threshold=3.5"
    resp = client.get(url)
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "ok"
    assert len(res["items"]) >= 1

    anomaly = res["items"][0]
    assert anomaly["value"] == 48.0
    assert anomaly["direction"] == "high"
    assert anomaly["score"] > 3.5

    # Strict PRD safety assertion check
    assert anomaly["is_official_warning"] is False
    assert anomaly["verification"] == "unverified"
    assert anomaly["disclaimer"] == "Statistical flag only. Not an official warning."
    assert "warning" not in anomaly["explanation"].lower()
    assert "alert" not in anomaly["explanation"].lower()
    assert "emergency" not in anomaly["explanation"].lower()


def test_analytics_edge_cases_and_error_handling(client: TestClient, db_session: Session):
    data = _seed_analytics_fixture(db_session)
    mumbai = data["mumbai"]
    now = data["now"]
    from_iso = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Summary: invalid location id (404)
    resp = client.get(f"/api/v1/analytics/summary?location_id=999999&from={from_iso}&to={to_iso}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"

    # 2. Summary: from >= to (422)
    resp = client.get(f"/api/v1/analytics/summary?from={to_iso}&to={from_iso}")
    assert resp.status_code == 422
    assert "strictly earlier" in resp.json()["error"]["message"]

    # 3. Summary: span > 366 days (422)
    too_far = (now - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = client.get(f"/api/v1/analytics/summary?from={too_far}&to={to_iso}")
    assert resp.status_code == 422
    assert "exceeds maximum allowed span" in resp.json()["error"]["message"]

    # 4. Timeseries: invalid interval (422)
    resp = client.get(
        f"/api/v1/analytics/timeseries?location_id={mumbai.id}&metric=temperature_c&interval=century&from={from_iso}&to={to_iso}"
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"

    # 5. Timeseries: invalid agg (422)
    resp = client.get(
        f"/api/v1/analytics/timeseries?location_id={mumbai.id}&metric=temperature_c&agg=median&from={from_iso}&to={to_iso}"
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"

    # 6. Timeseries: invalid kind (422)
    resp = client.get(
        f"/api/v1/analytics/timeseries?location_id={mumbai.id}&metric=temperature_c&kind=satellite&from={from_iso}&to={to_iso}"
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"

    # 7. Locations: invalid sort (422)
    resp = client.get(f"/api/v1/analytics/locations?sort=unknown_sort&from={from_iso}&to={to_iso}")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"

    # 8. Locations: sort by -record_count and coverage_pct
    resp = client.get(f"/api/v1/analytics/locations?sort=-record_count&from={from_iso}&to={to_iso}")
    assert resp.status_code == 200
    resp_cov = client.get(
        f"/api/v1/analytics/locations?sort=coverage_pct&from={from_iso}&to={to_iso}"
    )
    assert resp_cov.status_code == 200

    # 9. Events: invalid group_by (422)
    resp = client.get(f"/api/v1/analytics/events?group_by=invalid_col&from={from_iso}&to={to_iso}")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"

    # 10. Events: invalid location_id (404)
    resp = client.get(
        f"/api/v1/analytics/events?location_id=999999&group_by=event_type&from={from_iso}&to={to_iso}"
    )
    assert resp.status_code == 404

    # 11. Events: group_by day and location
    resp = client.get(f"/api/v1/analytics/events?group_by=day&from={from_iso}&to={to_iso}")
    assert resp.status_code == 200
    resp = client.get(f"/api/v1/analytics/events?group_by=location&from={from_iso}&to={to_iso}")
    assert resp.status_code == 200

    # 12. Anomalies: non-existent location (404)
    resp = client.get(
        f"/api/v1/analytics/anomalies?location_id=999999&metric=temperature_c&from={from_iso}&to={to_iso}"
    )
    assert resp.status_code == 404

    # 13. Anomalies: invalid metric (422)
    resp = client.get(
        f"/api/v1/analytics/anomalies?location_id={mumbai.id}&metric=nonsense&from={from_iso}&to={to_iso}"
    )
    assert resp.status_code == 422

    # 14. Anomalies: baseline_days out of bounds (422)
    resp = client.get(
        f"/api/v1/analytics/anomalies?location_id={mumbai.id}&metric=temperature_c&baseline_days=3&from={from_iso}&to={to_iso}"
    )
    assert resp.status_code == 422
    resp = client.get(
        f"/api/v1/analytics/anomalies?location_id={mumbai.id}&metric=temperature_c&baseline_days=500&from={from_iso}&to={to_iso}"
    )
    assert resp.status_code == 422

    # 15. Anomalies: threshold <= 0 (422)
    resp = client.get(
        f"/api/v1/analytics/anomalies?location_id={mumbai.id}&metric=temperature_c&threshold=-1.0&from={from_iso}&to={to_iso}"
    )
    assert resp.status_code == 422
