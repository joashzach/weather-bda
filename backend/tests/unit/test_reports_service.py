"""Unit tests for CitizenReportService business logic, validations, state transitions, and privacy."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.models.citizen_reports import CitizenReport
from app.db.models.locations import Location
from app.db.models.users import User
from app.repositories.reports import haversine_distance_km
from app.schemas.reports import (
    CitizenReportCreate,
    ReportReviewDecision,
)
from app.services.reports import (
    CitizenReportService,
    _to_public_report,
    _to_staff_report,
)


def test_haversine_distance_calculation():
    # Same point -> 0 km
    d0 = haversine_distance_km(28.6139, 77.2090, 28.6139, 77.2090)
    assert abs(d0) < 1e-4

    # New Delhi to Noida (~20 km)
    d_delhi_noida = haversine_distance_km(28.6139, 77.2090, 28.5355, 77.3910)
    assert 15 < d_delhi_noida < 25

    # New Delhi to Mumbai (~1150 km)
    d_delhi_mumbai = haversine_distance_km(28.6139, 77.2090, 19.0760, 72.8777)
    assert 1100 < d_delhi_mumbai < 1200


def test_create_report_event_time_too_far_future():
    db = MagicMock()
    future_time = datetime.now(UTC) + timedelta(minutes=15)
    body = CitizenReportCreate(
        event_type="heavy_rain",
        description="Heavy cloudburst flooding the street outside",
        latitude=28.6139,
        longitude=77.2090,
        event_time=future_time,
    )

    with pytest.raises(HTTPException) as exc:
        CitizenReportService.create_report(db, body, client_ip="127.0.0.1")

    assert exc.value.status_code == 422
    assert "future" in exc.value.detail["message"].lower()


def test_create_report_event_time_too_old():
    db = MagicMock()
    old_time = datetime.now(UTC) - timedelta(days=35)
    body = CitizenReportCreate(
        event_type="storm",
        description="Major storm took down power lines last month",
        latitude=28.6139,
        longitude=77.2090,
        event_time=old_time,
    )

    with pytest.raises(HTTPException) as exc:
        CitizenReportService.create_report(db, body, client_ip="127.0.0.1")

    assert exc.value.status_code == 422
    assert "30 days" in exc.value.detail["message"].lower()


def test_create_report_invalid_event_type():
    db = MagicMock()
    now = datetime.now(UTC)
    # Using model_construct or bypassing pydantic field validation
    body = CitizenReportCreate.model_construct(
        event_type="alien_invasion",
        description="Something weird in the sky happening right now",
        latitude=28.6139,
        longitude=77.2090,
        event_time=now,
        evidence=[],
    )

    with pytest.raises(HTTPException) as exc:
        CitizenReportService.create_report(db, body, client_ip="127.0.0.1")

    assert exc.value.status_code == 422
    assert "invalid event_type" in exc.value.detail["message"].lower()


def test_create_report_duplicate_conflict():
    db = MagicMock()
    now = datetime.now(UTC)
    body = CitizenReportCreate(
        event_type="flood",
        description="Water level rising rapidly over the pavement",
        latitude=28.6139,
        longitude=77.2090,
        event_time=now,
    )

    with patch(
        "app.services.reports.CitizenReportRepository.check_recent_duplicate", return_value=True
    ):
        with pytest.raises(HTTPException) as exc:
            CitizenReportService.create_report(db, body, client_ip="192.168.1.50")

        assert exc.value.status_code == 409
        assert "duplicate" in exc.value.detail["message"].lower()


def test_list_reports_invalid_sort():
    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        CitizenReportService.list_reports(db, sort="invalid_sort_key")

    assert exc.value.status_code == 422
    assert "invalid sort parameter" in exc.value.detail["message"].lower()


def test_list_reports_invalid_time_span():
    db = MagicMock()
    now = datetime.now(UTC)

    # from >= to
    with pytest.raises(HTTPException) as exc1:
        CitizenReportService.list_reports(db, from_time=now, to_time=now - timedelta(hours=1))
    assert exc1.value.status_code == 422

    # span > 31 days
    with pytest.raises(HTTPException) as exc2:
        CitizenReportService.list_reports(db, from_time=now - timedelta(days=35), to_time=now)
    assert exc2.value.status_code == 422
    assert "31 days" in exc2.value.detail["message"]


def test_list_reports_non_staff_status_filter_forbidden():
    db = MagicMock()
    # Anonymous / non-staff attempting status filter
    with pytest.raises(HTTPException) as exc:
        CitizenReportService.list_reports(db, current_user=None, status_filter="pending")

    assert exc.value.status_code == 403
    assert "staff credentials required" in exc.value.detail["message"].lower()


def test_privacy_serialization_strips_sensitive_fields():
    now = datetime.now(UTC)
    loc = Location(
        id=1,
        slug="delhi-in",
        name="Delhi",
        region="Delhi",
        country_code="IN",
        latitude=28.6139,
        longitude=77.2090,
    )
    rev = User(
        id=uuid.uuid4(),
        email="moderator@example.com",
        display_name="Mod Chief",
        password_hash="hash",
        role="reviewer",
    )
    report = CitizenReport(
        id=uuid.uuid4(),
        event_type="heavy_rain",
        severity="high",
        description="Heavy rain causing waterlogging near metro station",
        location_name="Connaught Place",
        latitude=28.6315,
        longitude=77.2167,
        location=loc,
        event_time=now,
        evidence=[
            {
                "type": "photo",
                "url": "https://secret-storage.internal/img1.jpg",
                "description": "Street view",
            }
        ],
        contact_email="citizen@private.com",
        status="verified",
        submitted_at=now,
        reviewed_at=now,
        reviewed_by=rev.id,
        reviewer=rev,
        ip_hash="abc123hash",
        tracking_token_hash="xyz789hash",
        row_version=2,
    )

    public_rep = _to_public_report(report)
    public_dict = public_rep.model_dump()

    # Forbidden keys in public schema
    assert "contact_email" not in public_dict
    assert "ip_hash" not in public_dict
    assert "tracking_token_hash" not in public_dict
    assert "row_version" not in public_dict
    assert "reviewed_by" not in public_dict
    assert public_dict["evidence"][0]["has_link"] is True
    assert "url" not in public_dict["evidence"][0]

    staff_rep = _to_staff_report(report)
    staff_dict = staff_rep.model_dump()

    # Staff schema includes administrative fields
    assert staff_dict["contact_email"] == "citizen@private.com"
    assert staff_dict["row_version"] == 2
    assert staff_dict["reviewed_by"]["id"] == rev.id
    assert staff_dict["evidence"][0]["url"] == "https://secret-storage.internal/img1.jpg"


def test_moderation_transition_rules():
    db = MagicMock()
    now = datetime.now(UTC)
    rev_user = User(
        id=uuid.uuid4(), email="rev@ex.com", display_name="R", role="reviewer", password_hash="h"
    )
    admin_user = User(
        id=uuid.uuid4(), email="adm@ex.com", display_name="A", role="admin", password_hash="h"
    )

    def _make_report(status_val: str, version: int):
        return CitizenReport(
            id=uuid.uuid4(),
            status=status_val,
            row_version=version,
            event_type="heavy_rain",
            description="Test report description",
            latitude=28.6139,
            longitude=77.2090,
            event_time=now,
            submitted_at=now,
            evidence=[],
        )

    # 1. Pending -> verify: notes not required
    rep1 = _make_report("pending", 1)
    with (
        patch(
            "app.services.reports.CitizenReportRepository.get_by_id_for_update", return_value=rep1
        ),
        patch("app.services.reports.CitizenReportRepository.get_by_id", return_value=rep1),
    ):
        CitizenReportService.review_report(
            db,
            rep1.id,
            ReportReviewDecision(decision="verify", expected_row_version=1),
            reviewer=rev_user,
        )
        assert rep1.status == "verified"
        assert rep1.row_version == 2

    # 2. Pending -> reject: notes or reason_code required (fails without)
    rep2 = _make_report("pending", 1)
    with patch(
        "app.services.reports.CitizenReportRepository.get_by_id_for_update", return_value=rep2
    ):
        with pytest.raises(HTTPException) as exc:
            CitizenReportService.review_report(
                db,
                rep2.id,
                ReportReviewDecision(decision="reject", expected_row_version=1),
                reviewer=rev_user,
            )
        assert exc.value.status_code == 422
        assert "notes or reason_code is required" in exc.value.detail["message"].lower()

    # 3. Verified -> reject (retraction): admin only! Reviewer gets 403
    rep3 = _make_report("verified", 2)

    with patch(
        "app.services.reports.CitizenReportRepository.get_by_id_for_update", return_value=rep3
    ):
        with pytest.raises(HTTPException) as exc:
            CitizenReportService.review_report(
                db,
                rep3.id,
                ReportReviewDecision(decision="reject", notes="Retracting", expected_row_version=2),
                reviewer=rev_user,
            )
        assert exc.value.status_code == 403

    # Admin succeeds on retraction
    with (
        patch(
            "app.services.reports.CitizenReportRepository.get_by_id_for_update", return_value=rep3
        ),
        patch("app.services.reports.CitizenReportRepository.get_by_id", return_value=rep3),
    ):
        CitizenReportService.review_report(
            db,
            rep3.id,
            ReportReviewDecision(
                decision="reject", notes="Retracting false report", expected_row_version=2
            ),
            reviewer=admin_user,
        )
        assert rep3.status == "rejected"
        assert rep3.row_version == 3

    # 4. Rejected -> reopen: admin only! Reviewer gets 403
    rep4 = _make_report("rejected", 3)
    with patch(
        "app.services.reports.CitizenReportRepository.get_by_id_for_update", return_value=rep4
    ):
        with pytest.raises(HTTPException) as exc:
            CitizenReportService.review_report(
                db,
                rep4.id,
                ReportReviewDecision(decision="reopen", notes="Reopening", expected_row_version=3),
                reviewer=rev_user,
            )
        assert exc.value.status_code == 403

    # Admin succeeds on reopen
    with (
        patch(
            "app.services.reports.CitizenReportRepository.get_by_id_for_update", return_value=rep4
        ),
        patch("app.services.reports.CitizenReportRepository.get_by_id", return_value=rep4),
    ):
        CitizenReportService.review_report(
            db,
            rep4.id,
            ReportReviewDecision(
                decision="reopen", notes="Reopening for secondary check", expected_row_version=3
            ),
            reviewer=admin_user,
        )
        assert rep4.status == "pending"
        assert rep4.row_version == 4

    # 5. Invalid transition: verified -> verify returns 409
    rep5 = _make_report("verified", 1)
    with patch(
        "app.services.reports.CitizenReportRepository.get_by_id_for_update", return_value=rep5
    ):
        with pytest.raises(HTTPException) as exc:
            CitizenReportService.review_report(
                db,
                rep5.id,
                ReportReviewDecision(decision="verify", expected_row_version=1),
                reviewer=admin_user,
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "invalid_transition"

    # 6. Concurrency conflict: expected_row_version mismatch returns 409 stale_version
    rep6 = _make_report("pending", 3)
    with patch(
        "app.services.reports.CitizenReportRepository.get_by_id_for_update", return_value=rep6
    ):
        with pytest.raises(HTTPException) as exc:
            CitizenReportService.review_report(
                db,
                rep6.id,
                ReportReviewDecision(decision="verify", expected_row_version=1),
                reviewer=rev_user,
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "stale_version"
