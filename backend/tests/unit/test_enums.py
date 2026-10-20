"""Unit tests verifying domain enumeration members and values."""

from app.core.enums import (
    RecordKind,
    ReportEventType,
    TrustLevel,
    UserRole,
)


def test_trust_levels() -> None:
    assert TrustLevel.OFFICIAL == "official"
    assert TrustLevel.PROVIDER_MODEL == "provider_model"
    assert TrustLevel.NEWS == "news"
    assert TrustLevel.CITIZEN == "citizen"


def test_user_roles() -> None:
    assert UserRole.ADMIN == "admin"
    assert UserRole.REVIEWER == "reviewer"


def test_record_kinds() -> None:
    assert RecordKind.OBSERVATION == "observation"
    assert RecordKind.FORECAST == "forecast"


def test_report_event_types() -> None:
    assert len(ReportEventType) == 12
    assert ReportEventType.HEAVY_RAIN == "heavy_rain"
    assert ReportEventType.FLOOD == "flood"
    assert ReportEventType.CYCLONE == "cyclone"
