"""SSRF-guarded outbound HTTP client factory enforcing DNS resolution safety and payload size caps."""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.enums import EnvironmentType

USER_AGENT = "WeatherBDA-Backend/1.0 (https://github.com/weather-bda)"


class SSRFSecurityError(ValueError):
    """Raised when an outbound URL violates SSRF safety rules."""


def validate_outbound_url(url: str) -> str:
    """Validate that an outbound URL strictly complies with SSRF security policies."""
    settings = get_settings()
    is_dev = settings.ENVIRONMENT == EnvironmentType.DEVELOPMENT
    allowed_hosts = settings.allowed_source_host_list

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    if scheme not in ("http", "https"):
        raise SSRFSecurityError(f"Disallowed URL scheme '{scheme}'. Only https is allowed.")

    if scheme == "http" and not is_dev:
        raise SSRFSecurityError("Plain HTTP is prohibited outside development environment.")

    if parsed.username or parsed.password:
        raise SSRFSecurityError("Embedded credentials in URLs are strictly prohibited.")

    if parsed.port and parsed.port not in (80, 443):
        raise SSRFSecurityError(f"Non-standard port '{parsed.port}' is prohibited.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityError("URL must contain a valid hostname.")

    # Reject IP-literal hostnames
    is_ip_literal = False
    try:
        ipaddress.ip_address(hostname)
        is_ip_literal = True
    except ValueError:
        pass

    if is_ip_literal:
        raise SSRFSecurityError(f"IP-literal hostname '{hostname}' is prohibited.")

    # Check allowed hostnames allow-list
    normalized_host = hostname.lower()
    if normalized_host not in allowed_hosts:
        raise SSRFSecurityError(f"Host '{normalized_host}' is not in ALLOWED_SOURCE_HOSTS.")

    # DNS resolution validation (reject loopback, private, link-local, multicast, metadata)
    try:
        addr_infos = socket.getaddrinfo(normalized_host, None)
    except socket.gaierror as e:
        raise SSRFSecurityError(f"Failed to resolve DNS for host '{normalized_host}': {e}") from e

    for addr_info in addr_infos:
        ip_str = addr_info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
                or (
                    isinstance(ip, ipaddress.IPv4Address)
                    and ip in ipaddress.IPv4Network("169.254.0.0/16")
                )
            ):
                raise SSRFSecurityError(
                    f"Host '{normalized_host}' resolved to forbidden IP '{ip_str}'."
                )
        except ValueError as e:
            raise SSRFSecurityError(f"Invalid resolved IP '{ip_str}': {e}") from e

    return url


class SafeHttpClient:
    """Synchronous HTTP client enforcing SSRF checks, explicit timeouts, and streaming size caps."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = get_settings()
        self.timeout = httpx.Timeout(
            connect=self.settings.HTTP_CONNECT_TIMEOUT,
            read=self.settings.HTTP_READ_TIMEOUT,
            write=10.0,
            pool=10.0,
        )
        self.headers = {"User-Agent": USER_AGENT}
        self.client = httpx.Client(
            transport=transport,
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=False,  # Re-validate every redirect hop manually
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "SafeHttpClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self._request_with_redirects("GET", url, **kwargs)

    def _request_with_redirects(self, method: str, url: str, **kwargs) -> httpx.Response:
        max_redirects = 3
        current_url = url

        for _ in range(max_redirects + 1):
            validate_outbound_url(current_url)

            # Stream request to enforce HTTP_MAX_RESPONSE_BYTES
            with self.client.stream(method, current_url, **kwargs) as response:
                if response.is_redirect:
                    next_url = response.headers.get("Location")
                    if not next_url:
                        raise SSRFSecurityError("Redirect response missing Location header.")
                    # Build absolute URL for redirect
                    resolved_next = str(response.url.join(next_url))
                    current_url = resolved_next
                    continue

                # Read body content with size cap
                content_chunks = []
                total_bytes = 0
                max_bytes = self.settings.HTTP_MAX_RESPONSE_BYTES

                for chunk in response.iter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise ValueError(
                            f"Response exceeded maximum allowed bytes ({max_bytes} bytes)"
                        )
                    content_chunks.append(chunk)

                # Return populated Response
                full_content = b"".join(content_chunks)
                return httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=full_content,
                    request=response.request,
                )

        raise SSRFSecurityError("Exceeded maximum allowed redirects (3)")
