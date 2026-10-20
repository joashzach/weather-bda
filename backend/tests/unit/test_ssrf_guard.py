"""Unit tests verifying SSRF guard rules and response size limits."""

import socket

import httpx
import pytest

from app.core.config import Settings
from app.core.http_client import SafeHttpClient, SSRFSecurityError, validate_outbound_url


def test_ssrf_rejects_disallowed_schemes() -> None:
    with pytest.raises(SSRFSecurityError) as exc:
        validate_outbound_url("ftp://api.open-meteo.com/data")
    assert "Disallowed URL scheme" in str(exc.value)


def test_ssrf_rejects_credentials_in_url() -> None:
    with pytest.raises(SSRFSecurityError) as exc:
        validate_outbound_url("https://admin:pass@api.open-meteo.com/data")
    assert "Embedded credentials" in str(exc.value)


def test_ssrf_rejects_non_standard_ports() -> None:
    with pytest.raises(SSRFSecurityError) as exc:
        validate_outbound_url("https://api.open-meteo.com:8443/data")
    assert "Non-standard port" in str(exc.value)


def test_ssrf_rejects_ip_literal_hostnames() -> None:
    with pytest.raises(SSRFSecurityError) as exc:
        validate_outbound_url("https://127.0.0.1/data")
    assert "IP-literal hostname" in str(exc.value)

    with pytest.raises(SSRFSecurityError) as exc:
        validate_outbound_url("https://169.254.169.254/latest/meta-data")
    assert "IP-literal hostname" in str(exc.value)


def test_ssrf_rejects_non_allowed_hostnames() -> None:
    with pytest.raises(SSRFSecurityError) as exc:
        validate_outbound_url("https://evil-attacker-site.com/weather")
    assert "not in ALLOWED_SOURCE_HOSTS" in str(exc.value)


def test_ssrf_rejects_private_and_metadata_ip_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate DNS resolving an allowed hostname to AWS/cloud metadata IP 169.254.169.254
    def mock_dns_resolve(host: str, port: int) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_dns_resolve)

    with pytest.raises(SSRFSecurityError) as exc:
        validate_outbound_url("https://api.open-meteo.com/v1/forecast")
    assert "resolved to forbidden IP" in str(exc.value)


def test_ssrf_rejects_loopback_ip_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate DNS rebinding resolving to 127.0.0.1
    def mock_dns_resolve(host: str, port: int) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_dns_resolve)

    with pytest.raises(SSRFSecurityError) as exc:
        validate_outbound_url("https://api.open-meteo.com/v1/forecast")
    assert "resolved to forbidden IP" in str(exc.value)


def test_safe_http_client_success(monkeypatch: pytest.MonkeyPatch) -> None:
    # Allow mock DNS resolution
    def mock_dns(host: str, port: int) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_dns)

    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"temperature": 25.5}))
    with SafeHttpClient(transport=transport) as client:
        res = client.get("https://api.open-meteo.com/v1/forecast")
        assert res.status_code == 200
        assert res.json() == {"temperature": 25.5}


def test_safe_http_client_oversize_payload_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_dns(host: str, port: int) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_dns)

    # Set HTTP_MAX_RESPONSE_BYTES to 100 bytes for testing
    settings = Settings(HTTP_MAX_RESPONSE_BYTES=100)
    monkeypatch.setattr("app.core.http_client.get_settings", lambda: settings)

    oversize_content = b"X" * 200
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=oversize_content))
    with SafeHttpClient(transport=transport) as client:
        with pytest.raises(ValueError) as exc:
            client.get("https://api.open-meteo.com/v1/forecast")
        assert "exceeded maximum allowed bytes" in str(exc.value)


def test_safe_http_client_excessive_redirects_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_dns(host: str, port: int) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_dns)

    # Mock an endless redirect loop
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            302, headers={"Location": "https://api.open-meteo.com/v1/forecast"}
        )
    )
    with SafeHttpClient(transport=transport) as client:
        with pytest.raises(SSRFSecurityError) as exc:
            client.get("https://api.open-meteo.com/v1/forecast")
        assert "Exceeded maximum allowed redirects" in str(exc.value)


def test_ssrf_guard_plain_http_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings
    from app.core.enums import EnvironmentType
    from app.core.http_client import validate_outbound_url

    prod_settings = Settings(
        ENVIRONMENT=EnvironmentType.PRODUCTION,
        JWT_SECRET="valid_production_secret_key_exceeding_32_chars!",
        IP_HASH_SECRET="valid_ip_hash_secret_16_chars!",
    )
    monkeypatch.setattr("app.core.http_client.get_settings", lambda: prod_settings)

    with pytest.raises(SSRFSecurityError) as exc:
        validate_outbound_url("http://api.open-meteo.com/test")
    assert "Plain HTTP is prohibited" in str(exc.value)


def test_ssrf_guard_missing_hostname() -> None:
    from app.core.http_client import validate_outbound_url

    with pytest.raises(SSRFSecurityError) as exc:
        validate_outbound_url("https://")
    assert "valid hostname" in str(exc.value)


def test_ssrf_guard_dns_resolution_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.http_client import validate_outbound_url

    def mock_dns_fail(host: str, port: int) -> list:
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", mock_dns_fail)

    with pytest.raises(SSRFSecurityError) as exc:
        validate_outbound_url("https://api.open-meteo.com/v1/forecast")
    assert "Failed to resolve DNS" in str(exc.value)


def test_safe_http_client_redirect_missing_location(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_dns(host: str, port: int) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_dns)

    # 302 without Location header
    transport = httpx.MockTransport(lambda req: httpx.Response(302, headers={}))
    with SafeHttpClient(transport=transport) as client:
        with pytest.raises(SSRFSecurityError) as exc:
            client.get("https://api.open-meteo.com/v1/forecast")
        assert "Redirect response missing Location header" in str(exc.value)
