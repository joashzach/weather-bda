"""Unit tests for statistical anomaly detection engine per PRD Section 9."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import numpy as np

from app.analytics.anomaly import detect_anomalies
from app.db.models.locations import Location


def test_anomaly_insufficient_baseline_samples():
    mock_db = MagicMock()
    # Mock scalars returning fewer than 168 rows
    mock_db.scalars.return_value.all.return_value = [25.0] * 100

    location = Location(id=1, slug="mumbai", name="Mumbai")
    now = datetime.now(UTC)

    resp = detect_anomalies(
        db=mock_db,
        location=location,
        metric="temperature_c",
        from_time=now - timedelta(days=7),
        to_time=now,
        baseline_days=30,
        threshold=3.5,
    )

    assert resp.status == "insufficient_data"
    assert len(resp.items) == 0
    assert "168" in resp.note


def test_anomaly_zero_mad():
    mock_db = MagicMock()
    # 200 identical values -> MAD will be 0.0
    mock_db.scalars.return_value.all.return_value = [25.0] * 200

    location = Location(id=1, slug="mumbai", name="Mumbai")
    now = datetime.now(UTC)

    resp = detect_anomalies(
        db=mock_db,
        location=location,
        metric="temperature_c",
        from_time=now - timedelta(days=7),
        to_time=now,
        baseline_days=30,
        threshold=3.5,
    )

    assert resp.status == "zero_mad"
    assert resp.baseline is not None
    assert resp.baseline.mad == 0.0
    assert len(resp.items) == 0
    assert "zero" in resp.note.lower()


def test_anomaly_detection_modified_z_score_and_safety_disclaimers():
    mock_db = MagicMock()

    # Generate 200 baseline readings with median 25.0, MAD ~ 1.0
    np.random.seed(42)
    baseline_noise = np.random.normal(loc=25.0, scale=1.0, size=200)
    mock_db.scalars.return_value.all.return_value = list(baseline_noise)

    now = datetime.now(UTC)
    t1 = now - timedelta(hours=3)
    t2 = now - timedelta(hours=2)
    t3 = now - timedelta(hours=1)

    # 3 target evaluation observations:
    # 25.5 (normal)
    # 45.0 (extreme high outlier: ~20 deg above median, modified z-score >> 3.5)
    # 5.0 (extreme low outlier: ~20 deg below median, modified z-score << -3.5)
    mock_db.execute.return_value.all.return_value = [
        (t1, 25.5),
        (t2, 45.0),
        (t3, 5.0),
    ]

    location = Location(id=1, slug="mumbai", name="Mumbai")

    resp = detect_anomalies(
        db=mock_db,
        location=location,
        metric="temperature_c",
        from_time=now - timedelta(days=7),
        to_time=now,
        baseline_days=30,
        threshold=3.5,
    )

    assert resp.status == "ok"
    assert len(resp.items) == 2

    high_item = next(it for it in resp.items if it.direction == "high")
    low_item = next(it for it in resp.items if it.direction == "low")

    assert high_item.value == 45.0
    assert high_item.score > 3.5
    assert "above" in high_item.explanation

    assert low_item.value == 5.0
    assert low_item.score < -3.5
    assert "below" in low_item.explanation

    # PRD Mandatory Safety Assertions:
    # "The API MUST NOT label an anomaly a warning, alert or emergency, and a test must assert the three fields above on every anomaly item."
    for item in resp.items:
        assert item.is_official_warning is False
        assert item.verification == "unverified"
        assert item.disclaimer == "Statistical flag only. Not an official warning."
        assert "warning" not in item.explanation.lower()
        assert "alert" not in item.explanation.lower()
        assert "emergency" not in item.explanation.lower()


def test_deps_helpers():
    from app.api.deps import get_optional_current_user, is_admin, is_staff
    from app.db.models.users import User

    assert get_optional_current_user() is None
    assert is_staff(None) is False
    assert is_admin(None) is False

    citizen = User(id=1, email="citizen@example.com", role="citizen")
    reviewer = User(id=2, email="reviewer@example.com", role="reviewer")
    admin = User(id=3, email="admin@example.com", role="admin")

    assert is_staff(citizen) is False
    assert is_staff(reviewer) is True
    assert is_staff(admin) is True

    assert is_admin(citizen) is False
    assert is_admin(reviewer) is False
    assert is_admin(admin) is True
