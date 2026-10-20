"""Unit tests for rate limit client IP extraction and reverse proxy trust."""

from unittest.mock import MagicMock

from fastapi import Request

from app.core.config import Settings
from app.core.rate_limit import get_client_ip


def test_get_client_ip_direct_peer(monkeypatch) -> None:
    request = MagicMock(spec=Request)
    request.client.host = "192.168.1.50"
    request.headers = {}

    ip = get_client_ip(request)
    assert ip == "192.168.1.50"


def test_get_client_ip_trusted_proxy(monkeypatch) -> None:
    settings = Settings(TRUSTED_PROXY_IPS="10.0.0.1, 10.0.0.2")
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: settings)

    request = MagicMock(spec=Request)
    request.client.host = "10.0.0.1"
    request.headers = {"X-Forwarded-For": "203.0.113.195, 10.0.0.1"}

    ip = get_client_ip(request)
    assert ip == "203.0.113.195"


def test_get_client_ip_untrusted_proxy_ignores_forwarded(monkeypatch) -> None:
    settings = Settings(TRUSTED_PROXY_IPS="10.0.0.1")
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: settings)

    request = MagicMock(spec=Request)
    request.client.host = "198.51.100.5"  # Untrusted client attempting header spoofing
    request.headers = {"X-Forwarded-For": "1.1.1.1"}

    ip = get_client_ip(request)
    assert ip == "198.51.100.5"


def test_get_client_ip_trusted_proxy_empty_forwarded(monkeypatch) -> None:
    settings = Settings(TRUSTED_PROXY_IPS="10.0.0.1")
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: settings)

    request = MagicMock(spec=Request)
    request.client.host = "10.0.0.1"
    request.headers = {"X-Forwarded-For": "   "}

    ip = get_client_ip(request)
    assert ip == "10.0.0.1"
