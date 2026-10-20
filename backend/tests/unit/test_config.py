"""Unit tests for configuration validation and environment constraints."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.enums import EnvironmentType


def test_cors_wildcard_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(CORS_ORIGINS="http://localhost:3000,*")
    assert "wildcard '*' is strictly forbidden" in str(exc.value)


def test_test_database_url_must_end_in_test() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(TEST_DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/weather_dev")
    assert "must end in '_test'" in str(exc.value)


def test_production_jwt_secret_validation() -> None:
    # Too short in production
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT=EnvironmentType.PRODUCTION,
            JWT_SECRET="short_secret",
            IP_HASH_SECRET="some_valid_ip_hash_secret_here",
        )
    assert "JWT_SECRET must be at least 32 characters" in str(exc.value)

    # Example secret in production
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT=EnvironmentType.PRODUCTION,
            JWT_SECRET="change_this_to_a_secure_random_32_character_string_at_least",
            IP_HASH_SECRET="some_valid_ip_hash_secret_here",
        )
    assert "JWT_SECRET cannot use the example value in production" in str(exc.value)


def test_production_ip_hash_secret_validation() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT=EnvironmentType.PRODUCTION,
            JWT_SECRET="valid_production_secret_key_exceeding_32_chars!",
            IP_HASH_SECRET="change_this_to_a_random_secret_for_hmac_ip_hashing",
        )
    assert "IP_HASH_SECRET must be set to a secure secret in production" in str(exc.value)


def test_derived_lists_parsing() -> None:
    settings = Settings(
        CORS_ORIGINS="http://localhost:5173, https://app.example.com",
        ALLOWED_SOURCE_HOSTS="api.open-meteo.com, MAUSAM.IMD.GOV.IN",
        TRUSTED_PROXY_IPS="10.0.0.1, 10.0.0.2",
    )
    assert settings.cors_origin_list == ["http://localhost:5173", "https://app.example.com"]
    assert settings.allowed_source_host_list == ["api.open-meteo.com", "mausam.imd.gov.in"]
    assert settings.trusted_proxy_list == ["10.0.0.1", "10.0.0.2"]


def test_cors_origins_empty_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(CORS_ORIGINS="   ")
    assert "CORS_ORIGINS cannot be empty" in str(exc.value)


def test_production_ip_hash_secret_too_short() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT=EnvironmentType.PRODUCTION,
            JWT_SECRET="valid_production_secret_key_exceeding_32_chars!",
            IP_HASH_SECRET="short",
        )
    assert "IP_HASH_SECRET must be set to a secure secret" in str(exc.value)


def test_get_db_session_lifecycle(monkeypatch) -> None:
    import contextlib
    from unittest.mock import MagicMock

    from app.api.deps import get_db

    mock_session = MagicMock()
    monkeypatch.setattr("app.db.session.SessionLocal", lambda: mock_session)

    gen = get_db()
    s = next(gen)
    assert s == mock_session
    with contextlib.suppress(StopIteration):
        next(gen)
    mock_session.close.assert_called_once()
