"""Rate limiting configuration with SlowAPI and safe client IP extraction."""

from fastapi import Request
from slowapi import Limiter

from app.core.config import get_settings
from app.core.enums import EnvironmentType


def get_client_ip(request: Request) -> str:
    """Safely extract client IP respecting TRUSTED_PROXY_IPS allow-list."""
    settings = get_settings()
    peer_ip = request.client.host if request.client else "127.0.0.1"

    if peer_ip in settings.trusted_proxy_list:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First non-empty client in chain
            client_ip = forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip

    return peer_ip


settings = get_settings()
# Rate limiting is disabled strictly in test environment
is_rate_limiting_enabled = settings.ENVIRONMENT != EnvironmentType.TEST

limiter = Limiter(
    key_func=get_client_ip,
    enabled=is_rate_limiting_enabled,
    default_limits=[settings.RATE_LIMIT_PUBLIC_READ],
)
